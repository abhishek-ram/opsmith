import yaml
from rich import print

from opsmith.deployment_strategies.base import BaseDeploymentStrategy
from opsmith.prompts import MONOLITHIC_MACHINE_REQUIREMENTS_PROMPT_TEMPLATE
from opsmith.spinner import WaitingSpinner
from opsmith.types import DeploymentConfig, DeploymentEnvironment, MachineRequirements


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
        print(
            "\n[bold blue]Estimating resource requirements for monolithic deployment...[/bold blue]"
        )

        services_yaml = yaml.dump([s.model_dump(mode="json") for s in deployment_config.services])
        infra_deps_yaml = yaml.dump(
            [i.model_dump(mode="json") for i in deployment_config.infra_deps]
        )

        prompt = MONOLITHIC_MACHINE_REQUIREMENTS_PROMPT_TEMPLATE.format(
            services_yaml=services_yaml, infra_deps_yaml=infra_deps_yaml
        )

        with WaitingSpinner(text="Waiting for LLM to estimate resources", delay=0.1):
            response = self.agent.run_sync(
                prompt, output_type=MachineRequirements, deps=self.agent_deps
            )

        machine_reqs = response.output
        print(
            f"[bold green]Estimated requirements: {machine_reqs.cpu} vCPUs,"
            f" {machine_reqs.ram_gb} GB RAM.[/bold green]"
        )

        cloud_provider = deployment_config.cloud_provider_instance

        print(f"\n[bold blue]Selecting instance type on {cloud_provider.name()}...[/bold blue]")

        with WaitingSpinner(text="Selecting instance type", delay=0.1):
            instance_type = cloud_provider.get_instance_type(
                machine_reqs.cpu, machine_reqs.ram_gb, environment.region
            )

        print(f"[bold green]Selected instance type: {instance_type}[/bold green]")

    def deploy(self, deployment_config: DeploymentConfig, environment: DeploymentEnvironment):
        """Deploys the application."""
        pass
