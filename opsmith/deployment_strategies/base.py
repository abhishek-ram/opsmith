import abc
import os
import platform
from importlib.metadata import entry_points
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Type

from pydantic_ai import Agent
from rich import print

from opsmith.agent import AgentDeps
from opsmith.types import DeploymentConfig, DeploymentEnvironment


class DeploymentStrategyRegistry:
    """A singleton registry for deployment strategies."""

    _instance: Optional["DeploymentStrategyRegistry"] = None
    _strategies: Dict[str, Type["BaseDeploymentStrategy"]]

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._strategies = {}
            cls._instance._load_builtin_strategies()
            cls._instance._load_plugin_strategies()
        return cls._instance

    def _load_builtin_strategies(self):
        """Load built-in strategies"""

        from opsmith.deployment_strategies.distributed import DistributedStrategy
        from opsmith.deployment_strategies.monolithic import MonolithicStrategy

        for strategy_cls in [MonolithicStrategy, DistributedStrategy]:
            self.register(strategy_cls)

    def _load_plugin_strategies(self):
        """Load strategies from installed packages via entry points"""
        discovered_entry_points = entry_points(group="opsmith.deployment_strategies")
        for entry_point in discovered_entry_points:
            try:
                strategy_cls = entry_point.load()
                self.register(strategy_cls)
                print(f"Loaded deployment strategy: {strategy_cls.name()}")
            except Exception as e:
                print(
                    "[yellow]Warning: Failed to load deployment strategy from entry point"
                    f" '{entry_point.name}': {e}[/yellow]"
                )

    def register(self, strategy_class: Type["BaseDeploymentStrategy"]):
        """Registers a deployment strategy."""
        # Not raising error on overwrite allows for easy extension/replacement
        self._strategies[strategy_class.name()] = strategy_class

    def get_strategy_class(self, strategy_name: str) -> Type["BaseDeploymentStrategy"]:
        """Retrieves a strategy class from the registry."""
        if strategy_name not in self._strategies:
            raise ValueError(f"Strategy '{strategy_name}' not found.")
        return self._strategies[strategy_name]

    @property
    def choices(self) -> List[Tuple[str, str]]:
        """Returns a list of (display text, value) tuples for use in prompts."""
        choices_list = []
        for name, strategy_class in sorted(self._strategies.items()):
            display_text = f"{name} - {strategy_class.description()}"
            choices_list.append((display_text, name))
        return choices_list


class BaseDeploymentStrategy(abc.ABC):
    """Abstract base class for deployment strategies."""

    @classmethod
    @abc.abstractmethod
    def name(cls) -> str:
        """The name of the deployment strategy."""
        raise NotImplementedError

    @classmethod
    @abc.abstractmethod
    def description(cls) -> str:
        """A brief description of the deployment strategy."""
        raise NotImplementedError

    def __init__(self, agent: Agent, src_dir: Path):
        self.agent = agent
        self.agent_deps = AgentDeps(src_dir=Path(src_dir))

    @abc.abstractmethod
    def setup_infra(self, deployment_config: DeploymentConfig, environment: DeploymentEnvironment):
        """Sets up the infrastructure for the deployment."""
        raise NotImplementedError

    @abc.abstractmethod
    def deploy(self, deployment_config: DeploymentConfig, environment: DeploymentEnvironment):
        """Deploys the application."""
        raise NotImplementedError

    @staticmethod
    def _get_ssh_public_key() -> str:
        """
        Checks for the existence of a local SSH public key file on the system and returns its
        contents if found. It searches through platform-specific commonly used directories
        and file names for SSH public keys and verifies their existence. If no public key
        is found, an error is raised guiding the user to generate one.

        :raises FileNotFoundError: If no SSH public key is found in the specified directories
            or with the expected names.
        :return: The content of the found SSH public key as a string.
        :rtype: str
        """
        print("\n[bold blue]Checking for local SSH public key...[/bold blue]")
        system = platform.system().lower()

        # Common SSH key names
        key_names = [
            "id_rsa",
            "id_dsa",
            "id_ecdsa",
            "id_ed25519",
            "id_rsa_github",
            "id_rsa_gitlab",
            "id_rsa_bitbucket",
            "github_rsa",
            "gitlab_rsa",
            "bitbucket_rsa",
        ]

        # Platform-specific SSH directory paths
        ssh_dirs = []

        if system in ["linux", "darwin"]:  # Linux and macOS
            home = Path.home()
            ssh_dirs.append(home / ".ssh")

            # Additional common locations on Unix-like systems
            if system == "linux":
                ssh_dirs.extend([Path("/etc/ssh"), Path("/usr/local/etc/ssh")])

        elif system == "windows":
            # Windows SSH key locations
            home = Path.home()
            ssh_dirs.extend(
                [
                    home / ".ssh",
                    home / "Documents" / ".ssh",
                    Path(os.environ.get("USERPROFILE", "")) / ".ssh",
                    Path("C:/ProgramData/ssh"),
                    Path("C:/Users") / os.environ.get("USERNAME", "") / ".ssh",
                ]
            )

            # OpenSSH for Windows locations
            if "PROGRAMFILES" in os.environ:
                ssh_dirs.append(Path(os.environ["PROGRAMFILES"]) / "OpenSSH")

        # Search in SSH directories
        for ssh_dir in ssh_dirs:
            if not ssh_dir.exists() or not ssh_dir.is_dir():
                continue
            # Look for specific key names with .pub extension
            for key_name in key_names:
                key_path = ssh_dir / f"{key_name}.pub"
                if key_path.exists() and key_path.is_file():
                    with open(key_path, "r", encoding="utf-8") as f:
                        print(f"[bold green]SSH public key found at {key_path}.[/bold green]")
                        return f.read().strip()

        print(
            "[bold red]SSH public key not found. Please generate one using 'ssh-keygen'.[/bold red]"
        )
        raise FileNotFoundError("SSH public key not found.")
