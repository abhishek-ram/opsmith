import abc
from importlib.metadata import entry_points
from typing import Dict, List, Optional, Tuple, Type

from rich import print

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

    def __init__(self, *args, **kwargs):
        pass

    @abc.abstractmethod
    def setup_infra(self, deployment_config: DeploymentConfig, environment: DeploymentEnvironment):
        """Sets up the infrastructure for the deployment."""
        raise NotImplementedError

    @abc.abstractmethod
    def deploy(self, deployment_config: DeploymentConfig, environment: DeploymentEnvironment):
        """Deploys the application."""
        raise NotImplementedError
