from enum import Enum
from pathlib import Path
from typing import List, Optional

import yaml
from pydantic import BaseModel, Field
from rich import print

from opsmith.agent import AgentDeps, ModelConfig, build_agent
from opsmith.cloud_providers.base import CloudProviderDetail
from opsmith.prompts import (
    DOCKERFILE_GENERATION_PROMPT_TEMPLATE,
    REPO_ANALYSIS_PROMPT_TEMPLATE,
)
from opsmith.repo_map import RepoMap
from opsmith.settings import settings
from opsmith.spinner import WaitingSpinner


class ServiceTypeEnum(str, Enum):
    """Enum for the different types of services that can be deployed."""

    BACKEND_API = "BACKEND_API"
    FRONTEND = "FRONTEND"
    FULL_STACK = "FULL_STACK"
    BACKEND_WORKER = "BACKEND_WORKER"


class DependencyTypeEnum(str, Enum):
    """Enum for the different types of infrastructure dependencies."""

    DATABASE = "DATABASE"
    CACHE = "CACHE"
    MESSAGE_QUEUE = "MESSAGE_QUEUE"
    SEARCH_ENGINE = "SEARCH_ENGINE"


class InfrastructureDependency(BaseModel):
    """Describes an infrastructure dependency for a service."""

    dependency_type: DependencyTypeEnum = Field(
        ..., description="The type of the infrastructure dependency."
    )
    provider: str = Field(
        ...,
        description=(
            "The specific provider of the dependency (e.g., 'postgresql', 'redis', 'rabbitmq',"
            " 'elasticsearch')."
        ),
    )
    version: Optional[str] = Field(
        None, description="The version of the infrastructure dependency, if identifiable."
    )


class EnvVarConfig(BaseModel):
    """Describes an environment variable configuration for a service."""

    key: str = Field(..., description="The name of the environment variable.")
    is_secret: bool = Field(
        ..., description="Whether the environment variable should be treated as a secret."
    )
    default_value: Optional[str] = Field(
        None,
        description="The default value of the environment variable, if present in the code.",
    )


class ServiceInfo(BaseModel):
    """Describes a single service to be deployed."""

    language: str = Field(..., description="The primary programming language of the service.")
    language_version: Optional[str] = Field(
        None, description="The specific version of the language, if identifiable."
    )
    service_type: ServiceTypeEnum = Field(..., description="The type of the service.")
    framework: Optional[str] = Field(
        None, description="The primary framework or library used, if any."
    )
    build_tool: Optional[str] = Field(
        None,
        description=(
            "The build tool used for the service, if identifiable (e.g., 'maven', 'gradle', 'npm',"
            " 'webpack')."
        ),
    )
    infra_deps: List[InfrastructureDependency] = Field(
        default_factory=list,
        description="A list of infrastructure dependencies required by the services.",
    )
    env_vars: List[EnvVarConfig] = Field(
        default_factory=list,
        description="A list of environment variable configurations required by the service.",
    )


class ServiceList(BaseModel):
    """List of services discovered within the repository."""

    services: List[ServiceInfo] = Field(
        ..., description="A list of services identified in the repository."
    )


class DeploymentConfig(ServiceList):
    """Describes the deployment config for the repository, listing all services."""

    app_name: str = Field(..., description="The name of the application.")
    cloud_provider: CloudProviderDetail = Field(..., discriminator="name")


class DockerfileContent(BaseModel):
    """Describes the dockerfile response from the agent, including the generated Dockerfile content and reasoning for the selection."""

    content: str = Field(
        ...,
        description="The final generated Dockerfile content.",
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
