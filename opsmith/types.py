from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field

from opsmith.cloud_providers.base import CloudProviderDetail


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


class InfrastructureProviderEnum(str, Enum):
    """Enum for the different types of infrastructure providers."""

    POSTGRESQL = "postgresql"
    MYSQL = "mysql"
    MONGODB = "mongodb"
    REDIS = "redis"
    RABBITMQ = "rabbitmq"
    KAFKA = "kafka"
    ELASTICSEARCH = "elasticsearch"
    WEAVIATE = "weaviate"
    USER_CHOICE = "user_choice"


COMPATIBLE_PROVIDERS = {
    DependencyTypeEnum.DATABASE: [
        InfrastructureProviderEnum.POSTGRESQL,
        InfrastructureProviderEnum.MYSQL,
        InfrastructureProviderEnum.MONGODB,
    ],
    DependencyTypeEnum.CACHE: [InfrastructureProviderEnum.REDIS],
    DependencyTypeEnum.MESSAGE_QUEUE: [
        InfrastructureProviderEnum.RABBITMQ,
        InfrastructureProviderEnum.KAFKA,
        InfrastructureProviderEnum.REDIS,
    ],
    DependencyTypeEnum.SEARCH_ENGINE: [
        InfrastructureProviderEnum.ELASTICSEARCH,
        InfrastructureProviderEnum.WEAVIATE,
    ],
}


class InfrastructureDependency(BaseModel):
    """Describes an infrastructure dependency for a service."""

    dependency_type: DependencyTypeEnum = Field(
        ..., description="The type of the infrastructure dependency."
    )
    provider: InfrastructureProviderEnum = Field(
        ...,
        description="The specific provider of the dependency.",
    )
    version: str = Field(
        "latest", description="The version of the infrastructure dependency, if identifiable."
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
    env_vars: List[EnvVarConfig] = Field(
        default_factory=list,
        description="A list of environment variable configurations required by the service.",
    )


class ServiceList(BaseModel):
    """List of services discovered within the repository."""

    services: List[ServiceInfo] = Field(
        ..., description="A list of services identified in the repository."
    )
    infra_deps: List[InfrastructureDependency] = Field(
        default_factory=list,
        description="A list of consolidated infrastructure dependencies required by all services.",
    )


class DeploymentEnvironment(BaseModel):
    """Describes a deployment environment."""

    name: str = Field(
        ..., description="The name of the environment (e.g., 'staging', 'production')."
    )
    region: str = Field(..., description="The cloud provider region for this environment.")


class DeploymentConfig(ServiceList):
    """Describes the deployment config for the repository, listing all services."""

    app_name: str = Field(..., description="The name of the application.")
    cloud_provider: CloudProviderDetail = Field(..., discriminator="name")
    environments: List[DeploymentEnvironment] = Field(
        default_factory=list, description="A list of deployment environments."
    )

    @property
    def environment_names(self) -> List[str]:
        return [env.name for env in self.environments]

    def get_environment(self, name: str) -> DeploymentEnvironment:
        """Retrieves an environment by name."""
        for env in self.environments:
            if env.name == name:
                return env
        raise ValueError(f"Environment '{name}' not found in the deployment configuration.")
