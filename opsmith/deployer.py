from pathlib import Path
from typing import List, Literal, Optional

import yaml
from pydantic import BaseModel, Field
from rich import print

from opsmith.cloud_providers.base import CloudProviderDetail
from opsmith.settings import settings


class InfrastructureDependency(BaseModel):
    """Describes an infrastructure dependency for a service."""

    dependency_type: Literal["database", "cache", "message_queue", "search_engine"] = Field(
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


class ServiceInfo(BaseModel):
    """Describes a single service to be deployed."""

    language: str = Field(..., description="The primary programming language of the service.")
    language_version: Optional[str] = Field(
        None, description="The specific version of the language, if identifiable."
    )
    service_type: Literal["backend_api", "frontend", "full_stack", "backend_worker"] = Field(
        ..., description="The type of the service."
    )
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


class DeploymentConfig(BaseModel):
    """Describes the deployment config for the repository, listing all services."""

    cloud_provider: CloudProviderDetail = Field(..., discriminator="name")
    services: List[ServiceInfo] = Field(
        ..., description="A list of services identified in the repository."
    )


class Deployer:
    def __init__(self):
        self.deployments_path = Path(settings.deployments_dir)
        self.config_file_name = "deployment_config.yml"
        self.config_file_path = self.deployments_path / self.config_file_name

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
