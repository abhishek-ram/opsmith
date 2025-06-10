from rich import print

from opsmith.agent import ModelConfig, build_agent
from opsmith.repo_map import RepoMap


class AnalyseRepo:
    def __init__(
        self,
        model_config: ModelConfig,
        root_dir: str,
        verbose: bool = False,
    ):
        self.agent = build_agent(
            model_config=model_config,
        )
        self.repo_map = RepoMap(
            root=root_dir,
            verbose=verbose,
        )

    def analyse(self):
        repo_map_str = self.repo_map.get_repo_map()
        print("Repo map generated, calling AI agent to analyse the repo.")
        print(repo_map_str)
