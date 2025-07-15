import base64
import shutil
import subprocess
from io import StringIO
from pathlib import Path
from typing import Dict, Optional, Tuple

import inquirer
import yaml
from dotenv import dotenv_values
from pydantic import BaseModel, Field
from rich import print

from opsmith.deployment_strategies.base import BaseDeploymentStrategy
from opsmith.exceptions import MonolithicDeploymentError
from opsmith.infra_provisioners.ansible_provisioner import AnsibleProvisioner
from opsmith.infra_provisioners.terraform_provisioner import TerraformProvisioner
from opsmith.prompts import (
    DOCKER_COMPOSE_GENERATION_PROMPT_TEMPLATE,
    DOCKER_COMPOSE_LOG_VALIDATION_PROMPT_TEMPLATE,
    MONOLITHIC_MACHINE_REQUIREMENTS_PROMPT_TEMPLATE,
)
from opsmith.spinner import WaitingSpinner
from opsmith.types import (
    DeploymentConfig,
    DeploymentEnvironment,
    MonolithicConfig,
    ServiceTypeEnum,
    VirtualMachineConfig,
)


class MachineRequirements(BaseModel):
    """Describes the machine requirements for a monolithic deployment."""

    cpu: int = Field(..., description="The number of virtual CPU cores required.")
    ram_gb: int = Field(..., description="The amount of RAM in gigabytes required.")


class DockerComposeLogValidation(BaseModel):
    """The result of validating the logs from a docker-compose deployment."""

    is_successful: bool = Field(
        ..., description="Whether the deployment is considered successful based on container logs."
    )
    reason: Optional[str] = Field(
        None, description="If not successful, an explanation of what went wrong."
    )


class DockerComposeContent(BaseModel):
    """Describes the generated docker-compose.yml file content."""

    content: str = Field(..., description="The final generated docker-compose.yml content.")
    env_file_content: str = Field(
        ...,
        description=(
            "The content of the .env file. This includes generated secrets for infrastructure and"
            " composed variables for application services."
        ),
    )
    reason: Optional[str] = Field(
        None, description="The reason for the failure of the last deployment attempt."
    )


class MonolithicDeploymentStrategy(BaseDeploymentStrategy):
    """Monolithic deployment strategy."""

    @classmethod
    def name(cls) -> str:
        return "Monolithic"

    @classmethod
    def description(cls) -> str:
        return "Deploys the entire application as a single unit."

    @staticmethod
    def _confirm_env_vars(
        deployment_config: DeploymentConfig,
        env_file_content: str,
        existing_confirmed_vars: Dict[str, str],
    ) -> Tuple[str, Dict[str, str]]:
        """
        Parses environment variables from LLM response, confirms with user, and returns updated content.
        """
        # Parse env_file_content from LLM
        env_file_vars = dotenv_values(stream=StringIO(env_file_content))

        env_defaults = deployment_config.get_env_var_defaults()

        # Prepare questions for inquirer
        questions = []
        for key, value in sorted(env_file_vars.items()):
            # Precedence: existing confirmed > llm > code default
            default_value = existing_confirmed_vars.get(key) or value or env_defaults.get(key)
            questions.append(
                inquirer.Text(
                    name=key,
                    message=f"Enter value for {key}",
                    default=default_value,
                )
            )

        # Prompt user
        print("\n[bold]Please confirm or provide values for environment variables:[/bold]")
        answers = inquirer.prompt(questions)

        # For the .env file, merge with precedence: user answers > existing confirmed > llm
        final_env_vars_for_file = {**env_file_vars, **answers}

        # Reconstruct env file content
        env_lines = [f'{key}="{value}"' for key, value in final_env_vars_for_file.items()]
        return "\n".join(env_lines), final_env_vars_for_file

    def _get_deploy_docker_compose_path(
        self, environment: DeploymentEnvironment
    ) -> Tuple[Path, Path]:
        deploy_compose_path = (
            self.deployments_path / "environments" / environment.name / "docker_compose_deploy"
        )
        deploy_compose_path.mkdir(parents=True, exist_ok=True)
        docker_compose_path = deploy_compose_path / "docker-compose.yml"

        return deploy_compose_path, docker_compose_path

    def _deploy_docker_compose(
        self,
        deployment_config: DeploymentConfig,
        environment: DeploymentEnvironment,
        environment_config: MonolithicConfig,
        env_file_content: str,
    ) -> str:
        """
        Deploys the docker-compose stack and returns container logs for validation.
        """
        print("\n[bold blue]Deploying docker-compose stack...[/bold blue]")
        ansible_user, instance_public_ip = (
            environment_config.virtual_machine.user,
            environment_config.virtual_machine.public_ip,
        )
        deploy_compose_path, docker_compose_path = self._get_deploy_docker_compose_path(environment)

        print("\n[bold blue]Attempting to deploy and get logs...[/bold blue]")
        ansible_runner = AnsibleProvisioner(working_dir=deploy_compose_path)
        ansible_runner.copy_template(
            "docker_compose_deploy", deployment_config.cloud_provider_instance.name().lower()
        )
        extra_vars = {
            "src_docker_compose": str(docker_compose_path),
            "dest_docker_compose": f"/home/{ansible_user}/app/docker-compose.yml",
            "env_file_content": env_file_content,
            "dest_env_file": f"/home/{ansible_user}/app/.env",
            "remote_user": ansible_user,
            "registry_host_url": environment_config.registry_url.split("/")[0],
        }

        try:
            outputs = ansible_runner.run_playbook(
                "main.yml",
                extra_vars=extra_vars,
                inventory=instance_public_ip,
                user=ansible_user,
            )
            logs_b64 = outputs.get("docker_logs", "")
            if logs_b64:
                return base64.b64decode(logs_b64.encode("ascii")).decode("utf-8")
            return ""
        except subprocess.CalledProcessError as e:
            return f"Ansible playbook execution failed.\nStdout:\n{e.stdout}\n\nStderr:\n{e.stderr}"

    def _generate_docker_compose(
        self,
        deployment_config: DeploymentConfig,
        environment: DeploymentEnvironment,
        images: Dict[str, str],
        environment_config: MonolithicConfig,
    ):
        print("\n[bold blue]Generating docker-compose file...[/bold blue]")

        template_dir = Path(__file__).parent.parent / "templates"
        base_compose_path = template_dir / "docker_compose_snippets" / "base.yml"
        with open(base_compose_path, "r", encoding="utf-8") as f:
            base_compose = f.read().format(app_name=deployment_config.app_name_slug)

        services_info = {}
        service_snippets_list = []
        for service in deployment_config.services:
            services_info[service.name_slug] = service.model_dump(mode="json")
            service_type_slug = service.service_type.value.lower()

            if service.service_type not in [
                ServiceTypeEnum.BACKEND_API,
                ServiceTypeEnum.BACKEND_WORKER,
                ServiceTypeEnum.FULL_STACK,
            ]:
                continue
            snippet_path = (
                template_dir / "docker_compose_snippets" / "services" / f"{service_type_slug}.yml"
            )
            if snippet_path.exists():
                with open(snippet_path, "r", encoding="utf-8") as f:
                    content = f.read()

                image_url = images.get(service.name_slug)
                if not image_url:
                    continue

                content = content.format(image_name=image_url, port=8000)
                service_snippets_list.append(f"# {service.name_slug}\n{content}")
        service_snippets = "\n\n".join(service_snippets_list)

        infra_snippets_list = []
        for infra in deployment_config.infra_deps:
            snippet_path = template_dir / "docker_compose_snippets" / f"{infra.provider}.yml"
            if snippet_path.exists():
                with open(snippet_path, "r", encoding="utf-8") as f:
                    content = f.read()
                    content = content.format(
                        version=infra.version, app_name=deployment_config.app_name_slug
                    )
                    infra_snippets_list.append(f"# {infra.provider}\n{content}")
        infra_snippets = "\n\n".join(infra_snippets_list)

        services_info_yaml = yaml.dump(services_info)

        max_attempts = 3
        confirmed_env_vars = {}
        messages = []
        for attempt in range(max_attempts):
            prompt = DOCKER_COMPOSE_GENERATION_PROMPT_TEMPLATE.format(
                base_compose=base_compose,
                services_info_yaml=services_info_yaml,
                service_snippets=service_snippets,
                infra_snippets=infra_snippets,
            )

            spinner_text = (
                "Waiting for LLM to generate docker-compose.yml"
                if attempt == 0
                else "Waiting for LLM to correct docker-compose.yml"
            )
            with WaitingSpinner(text=spinner_text, delay=0.1):
                docker_compose_response = self.agent.run_sync(
                    prompt,
                    output_type=DockerComposeContent,
                    deps=self.agent_deps,
                    message_history=messages,
                )

            deploy_compose_path, docker_compose_path = self._get_deploy_docker_compose_path(
                environment
            )
            with open(docker_compose_path, "w", encoding="utf-8") as f:
                f.write(docker_compose_response.output.content)
            print(f"[bold green]docker-compose.yml generated at {docker_compose_path}[/bold green]")

            confirmed_env_content, confirmed_env_vars = self._confirm_env_vars(
                deployment_config,
                docker_compose_response.output.env_file_content,
                confirmed_env_vars,
            )

            deployment_output = self._deploy_docker_compose(
                deployment_config,
                environment,
                environment_config,
                confirmed_env_content,
            )

            with WaitingSpinner("Validating deployment logs with LLM...", delay=0.1):
                log_validation_prompt = DOCKER_COMPOSE_LOG_VALIDATION_PROMPT_TEMPLATE.format(
                    container_logs=deployment_output
                )
                log_validation_response = self.agent.run_sync(
                    log_validation_prompt,
                    output_type=DockerComposeLogValidation,
                    deps=self.agent_deps,
                )

            if log_validation_response.output.is_successful:
                print("[bold green]Docker compose deployment was successful.[/bold green]")
                return

            print(
                f"[bold yellow]Attempt {attempt + 1}/{max_attempts} failed. Retrying with"
                " feedback...[/bold yellow]"
            )
            messages = (
                docker_compose_response.new_messages() + log_validation_response.new_messages()
            )
        else:
            print(
                "[bold red]Failed to generate and deploy a valid docker-compose file after"
                f" {max_attempts} attempts.[/bold red]"
            )

    def deploy(
        self,
        deployment_config: DeploymentConfig,
        environment: DeploymentEnvironment,
    ):
        """
        Creates a monolithic deployment environment using the provided deployment configuration and
        environment details. This function includes steps for setting up a container registry,
        building and pushing images, estimating resource requirements, selecting cloud provider
        instance types, creating a virtual machine, and generating Docker Compose configurations
        for deployment.

        :param deployment_config: Configuration object containing details of services, infrastructure
            dependencies, and other deployment settings.
        :type deployment_config: DeploymentConfig
        :param environment: Deployment environment details, including region and other configurations.
        :type environment: DeploymentEnvironment
        :return: None
        """
        public_services_count = sum(
            1
            for service in deployment_config.services
            if service.service_type in [ServiceTypeEnum.BACKEND_API, ServiceTypeEnum.FULL_STACK]
        )

        if public_services_count > 1:
            raise MonolithicDeploymentError(
                "Monolithic deployment strategy supports only one public-facing service"
                " (BACKEND_API or FULL_STACK)."
            )

        print(
            f"\n[bold blue]Setting up container registry for region '{environment.region}'...[/bold"
            " blue]"
        )
        registry_url = self._setup_container_registry(deployment_config, environment)
        images = self._build_and_push_images(deployment_config, environment, registry_url)

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

        questions = [
            inquirer.Text(
                "cpu",
                message="Confirm vCPU cores",
                default=str(machine_reqs.cpu),
                validate=lambda _, x: x.isdigit() and int(x) > 0,
            ),
            inquirer.Text(
                "ram_gb",
                message="Confirm RAM (GB)",
                default=str(machine_reqs.ram_gb),
                validate=lambda _, x: x.isdigit() and int(x) > 0,
            ),
        ]
        print("\n[bold]Please confirm machine requirements:[/bold]")
        answers = inquirer.prompt(questions)
        machine_reqs.cpu = int(answers["cpu"])
        machine_reqs.ram_gb = int(answers["ram_gb"])

        cloud_provider = deployment_config.cloud_provider_instance

        print(f"\n[bold blue]Selecting instance type on {cloud_provider.name()}...[/bold blue]")

        with WaitingSpinner(text="Selecting instance type", delay=0.1):
            instance_type, instance_arch = cloud_provider.get_instance_type(
                machine_reqs.cpu, machine_reqs.ram_gb, environment.region
            )
            print(
                f"[bold green]Selected instance type: {instance_type} ({instance_arch.value})[/bold"
                " green]"
            )

        print("\n[bold blue]Creating new virtual machine for monolithic deployment...[/bold blue]")
        instance_public_ip, ansible_user = self._create_virtual_machine(
            deployment_config, environment, instance_type, cloud_provider
        )

        env_config_path = self._get_env_config_path(environment.name)
        env_config = MonolithicConfig(
            registry_url=registry_url,
            virtual_machine=VirtualMachineConfig(
                instance_type=instance_type,
                architecture=instance_arch,
                public_ip=instance_public_ip,
                user=ansible_user,
            ),
        )
        env_config.save(env_config_path)
        print(f"Virtual machine details saved to {env_config_path}")

        self._generate_docker_compose(deployment_config, environment, images, env_config)

    def release(
        self,
        deployment_config: DeploymentConfig,
        environment: DeploymentEnvironment,
    ):
        """Deploys the application."""
        env_config_path = self._get_env_config_path(environment.name)
        env_config = MonolithicConfig.load(env_config_path)

        self._build_and_push_images(deployment_config, environment, env_config.registry_url)

        env_file_path = f"/home/{env_config.virtual_machine.user}/app/.env"
        fetched_files = self._fetch_remote_deployment_files(
            environment,
            env_config.virtual_machine.public_ip,
            env_config.virtual_machine.user,
            [env_file_path],
        )

        self._deploy_docker_compose(
            deployment_config,
            environment,
            env_config,
            fetched_files[0],
        )

    def destroy(
        self,
        deployment_config: DeploymentConfig,
        environment: DeploymentEnvironment,
    ):
        """Destroys the environment's infrastructure."""
        print("\n[bold blue]Destroying monolithic environment...[/bold blue]")

        # Destroy virtual machine
        cloud_provider = deployment_config.cloud_provider_instance
        infra_path = self.deployments_path / "environments" / environment.name / "virtual_machine"

        if infra_path.exists():
            env_config_path = self._get_env_config_path(environment.name)
            env_config = MonolithicConfig.load(env_config_path)
            if not env_config:
                print(
                    f"[bold red]Configuration for environment '{environment.name}' is missing or"
                    " incomplete. Cannot proceed with destruction.[/bold red]"
                )
                raise MonolithicDeploymentError(
                    f"Incomplete config for {environment.name}, cannot destroy."
                )

            tf = TerraformProvisioner(working_dir=infra_path)

            variables = {
                "app_name": deployment_config.app_name_slug,
                "instance_type": env_config.virtual_machine.instance_type,
                "region": environment.region,
                "ssh_pub_key": self._get_ssh_public_key(),
            }
            env_vars = cloud_provider.provider_detail.model_dump(mode="json")
            tf.destroy(variables, env_vars=env_vars)
        else:
            print(
                "[bold yellow]No virtual machine infrastructure found for environment"
                f" '{environment.name}'. Skipping VM destruction.[/bold yellow]"
            )

        # Clean up environment directory
        env_dir_path = self.deployments_path / "environments" / environment.name
        if env_dir_path.exists():
            try:
                shutil.rmtree(env_dir_path)
                print(f"[bold green]Environment directory '{env_dir_path}' deleted.[/bold green]")
            except OSError as e:
                print(
                    f"[bold red]Error deleting environment directory {env_dir_path}: {e}[/bold red]"
                )

        # Clean up the deployment config
        deployment_config.environments = [
            e for e in deployment_config.environments if e.name != environment.name
        ]
        deployment_config.save(self.deployments_path)
