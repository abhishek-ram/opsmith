from pathlib import Path
from typing import List, Literal, Optional

from pydantic import BaseModel, Field
from rich import print

from opsmith.agent import AgentDeps, ModelConfig, build_agent
from opsmith.prompts import REPO_ANALYSIS_PROMPT_TEMPLATE
from opsmith.repo_map import RepoMap
from opsmith.spinner import WaitingSpinner


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
    service_type: Literal["backend", "frontend", "full_stack", "worker"] = Field(
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

    services: List[ServiceInfo] = Field(
        ..., description="A list of services identified in the repository."
    )


class RepoScanner:
    def __init__(
        self,
        model_config: ModelConfig,
        src_dir: str,
        verbose: bool = False,
        instrument: bool = False,
    ):
        self.agent_deps = AgentDeps(src_dir=Path(src_dir))
        self.agent = build_agent(model_config=model_config, instrument=instrument)
        self.repo_map = RepoMap(
            src_dir=src_dir,
            verbose=verbose,
        )
        self.verbose = verbose

    def scan(self) -> DeploymentConfig:
        """
        Scans the repository to determine its deployment strategy.

        Generates a repository map, then uses an AI agent with a file reading tool
        to identify services and their characteristics.

        Returns:
            A DeploymentConfig object detailing the services to be deployed.
        """
        repo_map_str = self.repo_map.get_repo_map()
        if self.verbose:
            print("Repo map generated:")

        prompt = REPO_ANALYSIS_PROMPT_TEMPLATE.format(repo_map_str=repo_map_str)

        print("Calling AI agent to analyse the repo and determine deployment strategy...")
        with WaitingSpinner(text="Waiting for the LLM", delay=0.1):
            run_result = self.agent.run_sync(
                prompt, output_type=DeploymentConfig, deps=self.agent_deps
            )

        return run_result.output
