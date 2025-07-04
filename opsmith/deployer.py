import subprocess
from pathlib import Path
from typing import Optional

import yaml
from pydantic import BaseModel, Field
from rich import print

from opsmith.agent import AgentDeps, ModelConfig, build_agent
from opsmith.ansible import AnsibleRunner
from opsmith.cloud_providers import CloudProviderEnum
from opsmith.prompts import (
    DOCKERFILE_GENERATION_PROMPT_TEMPLATE,
    REPO_ANALYSIS_PROMPT_TEMPLATE,
)
from opsmith.repo_map import RepoMap
from opsmith.settings import settings
from opsmith.spinner import WaitingSpinner
from opsmith.terraform import TerraformRunner
from opsmith.types import (
    DeploymentConfig,
    DeploymentEnvironment,
    ServiceList,
    ServiceTypeEnum,
)
from opsmith.utils import slugify


class DockerfileContent(BaseModel):
    """Describes the dockerfile response from the agent, including the generated Dockerfile content and reasoning for the selection."""

    content: str = Field(
        ...,
        description="The final generated Dockerfile content.",
    )
    validation_output: str = Field(
        ...,
        description="The output from the final, successful call to the `build_dockerfile` tool.",
    )
    reason: Optional[str] = Field(
        None, description="The reasoning for the selection of the final Dockerfile content."
    )


class Deployer:
    def __init__(
        self,
        src_dir: str,
        model_config: ModelConfig,
        verbose: bool = False,
        instrument: bool = False,
    ):
        self.deployments_path = Path(src_dir).joinpath(settings.deployments_dir)
        self.config_file_name = "config.yml"
        self.config_file_path = self.deployments_path / self.config_file_name
        self.agent_deps = AgentDeps(src_dir=Path(src_dir))
        self.agent = build_agent(model_config=model_config, instrument=instrument)
        self.repo_map = RepoMap(
            src_dir=src_dir,
            verbose=verbose,
        )
        self.verbose = verbose

    def save_deployment_config(self, deployment_config: DeploymentConfig):
        """Saves the deployment configuration to a YAML file."""
        self.deployments_path.mkdir(parents=True, exist_ok=True)
        with open(self.config_file_path, "w") as f:
            yaml.dump(deployment_config.model_dump(mode="json"), f, indent=2)
        print(
            f"\n[bold blue]Deployment configuration saved to: {self.config_file_path}[/bold blue]"
        )

    def get_deployment_config(self) -> Optional[DeploymentConfig]:
        """Loads the deployment configuration from a YAML file."""
        if not self.config_file_path.exists():
            return None

        with open(self.config_file_path, "r") as f:
            config_data = yaml.safe_load(f)

        if config_data:
            return DeploymentConfig(**config_data)
        else:
            return None

    def setup_container_registry(
        self, deployment_config: DeploymentConfig, environment: DeploymentEnvironment
    ) -> str:
        """Sets up a container registry for the given region."""
        print(
            f"\n[bold blue]Setting up container registry for region '{environment.region}'...[/bold"
            " blue]"
        )

        app_name = deployment_config.app_name
        # Registry name should probably be unique per region for the app
        registry_name = slugify(f"{app_name}-{environment.region}")
        cloud_provider_details = deployment_config.cloud_provider
        provider_name = cloud_provider_details.name.lower()

        registry_infra_path = (
            self.deployments_path
            / "environments"
            / "global"
            / environment.region
            / "container_registry"
        )
        tf = TerraformRunner(working_dir=registry_infra_path)

        variables = {
            "app_name": app_name,
            "registry_name": registry_name,
            "region": environment.region,
        }
        if cloud_provider_details.name == CloudProviderEnum.GCP.value:
            variables["project_id"] = cloud_provider_details.project_id

        try:
            if not any(registry_infra_path.iterdir()):
                tf.copy_template("container_registry", provider_name, variables)

            tf.init_and_apply()

            outputs = tf.get_output()
            registry_url = outputs.get("registry_url")

            if registry_url:
                print(f"\n[bold green]Container registry created. URL: {registry_url}[/bold green]")
                return registry_url
            else:
                print(
                    "[bold red]Could not find 'registry_url' in TerraformRunner outputs.[/bold red]"
                )
                raise ValueError("Could not find 'registry_url' in TerraformRunner outputs.")

        except (FileNotFoundError, subprocess.CalledProcessError) as e:
            print(f"[bold red]Failed to set up container registry: {e}[/bold red]")
            raise

    def build_and_push_images(
        self,
        deployment_config: DeploymentConfig,
        environment: DeploymentEnvironment,
        registry_url: str,
    ):
        """Builds and pushes Docker images for each service."""
        print("\n[bold blue]Starting to build and push images...[/bold blue]")

        buildable_service_types = [
            ServiceTypeEnum.BACKEND_API,
            ServiceTypeEnum.FULL_STACK,
            ServiceTypeEnum.BACKEND_WORKER,
        ]

        for service in deployment_config.services:
            if service.service_type not in buildable_service_types:
                continue

            # This logic is from generate_dockerfiles
            service_dir_slug = f"{service.language}_{service.service_type.value}".replace(
                " ", "_"
            ).lower()
            service_image_dir = "images"
            dockerfile_path_abs = (
                self.deployments_path / service_image_dir / service_dir_slug / "Dockerfile"
            )

            if not dockerfile_path_abs.exists():
                print(
                    f"[bold yellow]Dockerfile for {service_dir_slug} not found at"
                    f" {dockerfile_path_abs}, skipping build.[/bold yellow]"
                )
                continue

            image_name_slug = service_dir_slug

            print(f"\n[bold]Building and pushing image for {image_name_slug}...[/bold]")

            build_infra_path = (
                self.deployments_path
                / "environments"
                / environment.name
                / "build_images"
                / image_name_slug
            )

            ansible_runner = AnsibleRunner(working_dir=build_infra_path)

            cloud_provider_details = deployment_config.cloud_provider
            provider_name = cloud_provider_details.name.lower()

            extra_vars = {
                "dockerfile_path": str(self.agent_deps.src_dir),
                "dockerfile_name": str(dockerfile_path_abs),
                "image_name_slug": image_name_slug,
                "image_tag_name": "latest",
                "region": environment.region,
                "registry_url": registry_url,
            }

            ansible_runner.copy_template("docker_build_push", provider_name, {})
            ansible_runner.run_playbook("main.yml", extra_vars)

            print(f"[green]Successfully built and pushed image for {image_name_slug}[/green]")

    def generate_dockerfiles(
        self,
    ):
        """Generates Dockerfiles for each service in the deployment configuration."""
        print("\n[bold blue]Starting Dockerfile generation...[/bold blue]")
        deployment_config = self.get_deployment_config()

        buildable_service_types = [
            ServiceTypeEnum.BACKEND_API,
            ServiceTypeEnum.FULL_STACK,
            ServiceTypeEnum.BACKEND_WORKER,
        ]

        for idx, service in enumerate(deployment_config.services):
            if service.service_type not in buildable_service_types:
                print(
                    f"\n[bold yellow]Dockerfile not needed for service {service.service_type},"
                    " skipping.[/bold yellow]"
                )
                continue

            service_name_slug = f"{service.language}_{service.service_type.value}".replace(
                " ", "_"
            ).lower()
            service_dir_name = "images"
            service_dir_path = self.deployments_path / service_dir_name / service_name_slug
            service_dir_path.mkdir(parents=True, exist_ok=True)
            dockerfile_path_abs = service_dir_path / "Dockerfile"
            print(
                f"\n[bold]Generating Dockerfile for service {idx + 1}:"
                f" {service.language} ({service.service_type})...[/bold]"
            )

            service_info_yaml = yaml.dump(service.model_dump(mode="json"), indent=2)
            prompt = DOCKERFILE_GENERATION_PROMPT_TEMPLATE.format(
                service_info_yaml=service_info_yaml,
                repo_map_str=self.repo_map.get_repo_map(),
            )
            with WaitingSpinner(text="Waiting for the LLM to generate the Dockerfile", delay=0.1):
                response = self.agent.run_sync(
                    prompt, deps=self.agent_deps, output_type=DockerfileContent
                )
                dockerfile_content = response.output

                # Write ensures the dockerfile content received from the agent to the deployments_dir.
                with open(dockerfile_path_abs, "w", encoding="utf-8") as f:
                    f.write(dockerfile_content.content)
                print(f"[green]Dockerfile saved to: {dockerfile_path_abs}[/green]")

        print("\n[bold blue]Dockerfile generation complete.[/bold blue]")

    def detect_services(self) -> ServiceList:
        """
        Scans the repository to determine the services to be deployed, using the AI agent.

        Generates a repository map, then uses an AI agent with a file reading tool
        to identify services and their characteristics.

        Returns:
            A ServiceList object detailing the services to be deployed.
        """
        repo_map_str = self.repo_map.get_repo_map()
        if self.verbose:
            print("Repo map generated:")

        prompt = REPO_ANALYSIS_PROMPT_TEMPLATE.format(repo_map_str=repo_map_str)

        print("Calling AI agent to analyse the repo and determine the services...")
        with WaitingSpinner(text="Waiting for the LLM", delay=0.1):
            run_result = self.agent.run_sync(prompt, output_type=ServiceList, deps=self.agent_deps)

        return run_result.output
