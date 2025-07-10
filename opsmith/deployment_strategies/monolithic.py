import subprocess

import yaml
from rich import print

from opsmith.deployment_strategies.base import BaseDeploymentStrategy
from opsmith.infra_provisioners.terraform_provisioner import TerraformProvisioner
from opsmith.prompts import MONOLITHIC_MACHINE_REQUIREMENTS_PROMPT_TEMPLATE
from opsmith.settings import settings
from opsmith.spinner import WaitingSpinner
from opsmith.types import DeploymentConfig, DeploymentEnvironment, MachineRequirements
from opsmith.utils import slugify


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

        print("\n[bold blue]Provisioning monolithic infrastructure...[/bold blue]")
        provider_name = cloud_provider.name().lower()
        infra_path = (
            self.agent_deps.src_dir
            / settings.deployments_dir
            / "environments"
            / environment.name
            / "monolithic_vm"
        )
        tf = TerraformProvisioner(working_dir=infra_path)

        variables = {
            "app_name": slugify(deployment_config.app_name),
            "instance_type": instance_type,
            "region": environment.region,
            "ssh_pub_key": self._get_ssh_public_key(),
        }
        env_vars = cloud_provider.provider_detail.model_dump(mode="json")

        try:
            if not any(infra_path.iterdir()):
                tf.copy_template("monolithic_vm", provider_name)

            tf.init_and_apply(variables, env_vars=env_vars)

            outputs = tf.get_output()
            print("[bold green]Monolithic infrastructure provisioned successfully.[/bold green]")
            if outputs:
                print("[bold green]Outputs:[/bold green]")
                print(yaml.dump(outputs))

        except (FileNotFoundError, subprocess.CalledProcessError) as e:
            print(f"[bold red]Failed to set up monolithic infrastructure: {e}[/bold red]")
            raise

    def deploy(self, deployment_config: DeploymentConfig, environment: DeploymentEnvironment):
        """Deploys the application."""
        pass
