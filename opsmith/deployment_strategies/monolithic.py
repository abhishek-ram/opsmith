from pathlib import Path
from typing import Dict, Tuple

import yaml
from pydantic import BaseModel, Field
from rich import print

from opsmith.deployment_strategies.base import BaseDeploymentStrategy
from opsmith.infra_provisioners.ansible_provisioner import AnsibleProvisioner
from opsmith.infra_provisioners.terraform_provisioner import TerraformProvisioner
from opsmith.prompts import (
    DOCKER_COMPOSE_GENERATION_PROMPT_TEMPLATE,
    MONOLITHIC_MACHINE_REQUIREMENTS_PROMPT_TEMPLATE,
)
from opsmith.spinner import WaitingSpinner
from opsmith.types import (
    DeploymentConfig,
    DeploymentEnvironment,
    MachineRequirements,
    ServiceTypeEnum,
)
from opsmith.utils import slugify


class DockerComposeContent(BaseModel):
    """Describes the generated docker-compose.yml file content."""

    content: str = Field(..., description="The final generated docker-compose.yml content.")
    env_file_content: str = Field(
        ...,
        description=(
            "The content of the .env file. This includes generated secrets for infrastructure and"
            " composed variables for application services."
        ),
    )


class MonolithicStrategy(BaseDeploymentStrategy):
    """Monolithic deployment strategy."""

    @classmethod
    def name(cls) -> str:
        return "Monolithic"

    @classmethod
    def description(cls) -> str:
        return "Deploys the entire application as a single unit."

    def _deploy_docker_compose(
        self,
        deployment_config: DeploymentConfig,
        environment: DeploymentEnvironment,
        instance_public_ip: str,
        ansible_user: str,
        registry_url: str,
        docker_compose_response,
    ):
        print("\n[bold blue]Deploying docker-compose stack...[/bold blue]")
        deploy_compose_path = (
            self.deployments_path / "environments" / environment.name / "docker_compose_deploy"
        )
        docker_compose_path = deploy_compose_path / "docker-compose.yml"

        env_file_content = docker_compose_response.env_file_content

        docker_compose_content = docker_compose_response.content
        with open(docker_compose_path, "w", encoding="utf-8") as f:
            f.write(docker_compose_content)
        print(f"[bold green]docker-compose.yml generated at {docker_compose_path}[/bold green]")

        print("\n[bold blue]Deploying docker-compose stack...[/bold blue]")
        ansible_runner = AnsibleProvisioner(working_dir=deploy_compose_path)
        ansible_runner.copy_template(
            "docker_compose_deploy", deployment_config.cloud_provider_instance.name().lower()
        )
        extra_vars = {
            "src_docker_compose": str(docker_compose_path),
            "dest_docker_compose": f"/home/{ansible_user}/app/docker-compose.yml",
            "env_file_content": env_file_content,
            "dest_env_file": f"/home/{ansible_user}/app/.env",
            "remote_user": ansible_user,
            "registry_host_url": registry_url.split("/")[0],
        }

        ansible_runner.run_playbook(
            "main.yml",
            extra_vars=extra_vars,
            inventory=instance_public_ip,
            user=ansible_user,
        )
        print("[bold green]Docker-compose stack deployed.[/bold green]")

    def _generate_docker_compose(
        self,
        deployment_config: DeploymentConfig,
        environment: DeploymentEnvironment,
        images: Dict[str, str],
        instance_public_ip: str,
        ansible_user: str,
        registry_url: str,
    ):
        print("\n[bold blue]Generating docker-compose file...[/bold blue]")

        template_dir = Path(__file__).parent.parent / "templates"
        base_compose_path = template_dir / "docker_compose_snippets" / "base.yml"
        with open(base_compose_path, "r", encoding="utf-8") as f:
            base_compose = f.read().format(app_name=slugify(deployment_config.app_name))

        service_snippets = {}
        services_info = {}
        for service in deployment_config.services:
            service_name_slug = f"{service.language}_{service.service_type.value}".replace(
                " ", "_"
            ).lower()
            services_info[service_name_slug] = service.model_dump(mode="json")
            service_type_slug = service.service_type.value.lower()

            if service.service_type not in [
                ServiceTypeEnum.BACKEND_API,
                ServiceTypeEnum.BACKEND_WORKER,
                ServiceTypeEnum.FULL_STACK,
            ]:
                continue
            snippet_path = (
                template_dir / "docker_compose_snippets" / "services" / f"{service_type_slug}.yml"
            )
            if snippet_path.exists():
                with open(snippet_path, "r", encoding="utf-8") as f:
                    content = f.read()

                image_url = images.get(service_name_slug)
                if not image_url:
                    continue

                content = content.format(image_name=image_url, port=8000)
                service_snippets[service_name_slug] = content

        infra_snippets = {}
        for infra in deployment_config.infra_deps:
            snippet_path = template_dir / "docker_compose_snippets" / f"{infra.provider}.yml"
            if snippet_path.exists():
                with open(snippet_path, "r", encoding="utf-8") as f:
                    content = f.read()
                    content = content.format(
                        version=infra.version, app_name=slugify(deployment_config.app_name)
                    )
                    infra_snippets[infra.provider] = content

        services_info_yaml = yaml.dump(services_info)
        prompt = DOCKER_COMPOSE_GENERATION_PROMPT_TEMPLATE.format(
            base_compose=base_compose,
            services_info_yaml=services_info_yaml,
            service_snippets=yaml.dump(service_snippets),
            infra_snippets=yaml.dump(infra_snippets),
        )

        with WaitingSpinner(text="Waiting for LLM to generate docker-compose.yml", delay=0.1):
            response = self.agent.run_sync(
                prompt, output_type=DockerComposeContent, deps=self.agent_deps
            )

        self._deploy_docker_compose(
            deployment_config,
            environment,
            instance_public_ip,
            ansible_user,
            registry_url,
            response.output,
        )

    def setup_infra(
        self,
        deployment_config: DeploymentConfig,
        environment: DeploymentEnvironment,
    ):
        """Sets up the infrastructure for the deployment."""
        print(
            f"\n[bold blue]Setting up container registry for region '{environment.region}'...[/bold"
            " blue]"
        )
        registry_url = self._setup_container_registry(deployment_config, environment)
        images = self._build_and_push_images(deployment_config, environment, registry_url)

        print(
            "\n[bold blue]Estimating resource requirements for monolithic deployment...[/bold blue]"
        )

        services_yaml = yaml.dump([s.model_dump(mode="json") for s in deployment_config.services])
        infra_deps_yaml = yaml.dump(
            [i.model_dump(mode="json") for i in deployment_config.infra_deps]
        )

        prompt = MONOLITHIC_MACHINE_REQUIREMENTS_PROMPT_TEMPLATE.format(
            services_yaml=services_yaml, infra_deps_yaml=infra_deps_yaml
        )

        with WaitingSpinner(text="Waiting for LLM to estimate resources", delay=0.1):
            response = self.agent.run_sync(
                prompt, output_type=MachineRequirements, deps=self.agent_deps
            )

        machine_reqs = response.output
        print(
            f"[bold green]Estimated requirements: {machine_reqs.cpu} vCPUs,"
            f" {machine_reqs.ram_gb} GB RAM.[/bold green]"
        )

        cloud_provider = deployment_config.cloud_provider_instance

        print(f"\n[bold blue]Selecting instance type on {cloud_provider.name()}...[/bold blue]")

        with WaitingSpinner(text="Selecting instance type", delay=0.1):
            instance_type = cloud_provider.get_instance_type(
                machine_reqs.cpu, machine_reqs.ram_gb, environment.region
            )
            print(f"[bold green]Selected instance type: {instance_type}[/bold green]")

        print("\n[bold blue]Creating new virtual machine for monolithic deployment...[/bold blue]")
        instance_public_ip, ansible_user = self._create_virtual_machine(
            deployment_config, environment, instance_type, cloud_provider
        )

        self._generate_docker_compose(
            deployment_config, environment, images, instance_public_ip, ansible_user, registry_url
        )

    def _load_virtual_machine_details(
        self,
        environment: DeploymentEnvironment,
    ) -> Tuple[str, str]:
        print("\n[bold blue]Loading monolithic infrastructure details...[/bold blue]")
        infra_path = self.deployments_path / "environments" / environment.name / "virtual_machine"
        tf = TerraformProvisioner(working_dir=infra_path)
        outputs = tf.get_output()

        instance_public_ip = outputs.get("instance_public_ip")
        if not instance_public_ip:
            print("[bold red]Could not find 'instance_public_ip' in Terraform outputs.[/bold red]")
            raise ValueError("Could not find 'instance_public_ip' in Terraform outputs.")

        ansible_user = outputs.get("ansible_user")
        if not ansible_user:
            print("[bold red]Could not find 'ansible_user' in Terraform outputs.[/bold red]")
            raise ValueError("Could not find 'ansible_user' in Terraform outputs.")

        return instance_public_ip, ansible_user

    def deploy(
        self,
        deployment_config: DeploymentConfig,
        environment: DeploymentEnvironment,
    ):
        """Deploys the application."""
        instance_public_ip, ansible_user = self._load_virtual_machine_details(environment)

        registry_url = self._setup_container_registry(deployment_config, environment)
        images = self._build_and_push_images(deployment_config, environment, registry_url)

        self._generate_docker_compose(
            deployment_config, environment, images, instance_public_ip, ansible_user, registry_url
        )
