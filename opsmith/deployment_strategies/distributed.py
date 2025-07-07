from opsmith.deployment_strategies.base import BaseDeploymentStrategy
from opsmith.types import DeploymentConfig, DeploymentEnvironment


class DistributedStrategy(BaseDeploymentStrategy):
    """Distributed deployment strategy."""

    @classmethod
    def name(cls) -> str:
        return "Distributed"

    @classmethod
    def description(cls) -> str:
        return "Deploys the application as multiple independent services."

    def setup_infra(self, deployment_config: DeploymentConfig, environment: DeploymentEnvironment):
        """Sets up the infrastructure for the deployment."""
        pass

    def deploy(self, deployment_config: DeploymentConfig, environment: DeploymentEnvironment):
        """Deploys the application."""
        pass
