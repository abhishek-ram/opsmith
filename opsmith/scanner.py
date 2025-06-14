from pathlib import Path
from typing import List

from pydantic import BaseModel
from rich import print

from opsmith.agent import AgentDeps, ModelConfig, build_agent
from opsmith.deployer import ServiceInfo
from opsmith.prompts import REPO_ANALYSIS_PROMPT_TEMPLATE
from opsmith.repo_map import RepoMap
from opsmith.spinner import WaitingSpinner


class ServiceList(BaseModel):
    """List of services discovered within the repository."""

    services: List[ServiceInfo]


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

    def scan(self) -> ServiceList:
        """
        Scans the repository to determine its deployment strategy.

        Generates a repository map, then uses an AI agent with a file reading tool
        to identify services and their characteristics.

        Returns:
            A ServiceList object detailing the services to be deployed.
        """
        repo_map_str = self.repo_map.get_repo_map()
        if self.verbose:
            print("Repo map generated:")

        prompt = REPO_ANALYSIS_PROMPT_TEMPLATE.format(repo_map_str=repo_map_str)

        print("Calling AI agent to analyse the repo and determine deployment strategy...")
        with WaitingSpinner(text="Waiting for the LLM", delay=0.1):
            run_result = self.agent.run_sync(prompt, output_type=ServiceList, deps=self.agent_deps)

        return run_result.output
