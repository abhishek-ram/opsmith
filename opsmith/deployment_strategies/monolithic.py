from opsmith.deployment_strategies.base import BaseDeploymentStrategy
from opsmith.types import DeploymentConfig, DeploymentEnvironment


class MonolithicStrategy(BaseDeploymentStrategy):
    """Monolithic deployment strategy."""

    @classmethod
    def name(cls) -> str:
        return "Monolithic"

    @classmethod
    def description(cls) -> str:
        return "Deploys the entire application as a single unit."

    def setup_infra(self, deployment_config: DeploymentConfig, environment: DeploymentEnvironment):
        """Sets up the infrastructure for the deployment."""
        pass

    def deploy(self, deployment_config: DeploymentConfig, environment: DeploymentEnvironment):
        """Deploys the application."""
        pass
