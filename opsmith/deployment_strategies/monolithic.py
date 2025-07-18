import base64
import shutil
import subprocess
from io import StringIO
from pathlib import Path
from typing import Dict, Optional, Tuple

import inquirer
import jinja2
import yaml
from dotenv import dotenv_values
from pydantic import BaseModel, Field
from rich import print

from opsmith.cloud_providers.base import MachineType, MachineTypeList
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
    MonolithicDeploymentState,
    ServiceTypeEnum,
    VirtualMachineState,
)


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

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.docker_compose_snippets_env = jinja2.Environment(
            loader=jinja2.FileSystemLoader(self.templates_dir / "docker_compose_snippets"),
            autoescape=False,
        )

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
        environment_state: MonolithicDeploymentState,
        env_file_content: str,
    ) -> str:
        """
        Deploys the docker-compose stack and returns container logs for validation.
        """
        print("\n[bold blue]Deploying docker-compose stack...[/bold blue]")
        ansible_user, instance_public_ip = (
            environment_state.virtual_machine.user,
            environment_state.virtual_machine.public_ip,
        )
        deploy_compose_path, docker_compose_path = self._get_deploy_docker_compose_path(environment)

        print("\n[bold blue]Attempting to deploy and get logs...[/bold blue]")
        ansible_runner = AnsibleProvisioner(working_dir=deploy_compose_path)
        ansible_runner.copy_template(
            "docker_compose_deploy", deployment_config.cloud_provider_instance.name().lower()
        )

        traefik_template = self.docker_compose_snippets_env.get_template("traefik.yml")
        traefik_content = traefik_template.render(domain_email=environment.domain_email or "")

        extra_vars = {
            "src_docker_compose": str(docker_compose_path),
            "dest_docker_compose": f"/home/{ansible_user}/app/docker-compose.yml",
            "env_file_content": env_file_content,
            "dest_env_file": f"/home/{ansible_user}/app/.env",
            "remote_user": ansible_user,
            "registry_host_url": environment_state.registry_url.split("/")[0],
            "traefik_yml_content": traefik_content,
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
        environment_state: MonolithicDeploymentState,
    ):
        print("\n[bold blue]Generating docker-compose file...[/bold blue]")

        base_compose_template = self.docker_compose_snippets_env.get_template("base.yml")
        base_compose = base_compose_template.render(app_name=deployment_config.app_name_slug)

        services_info = {}
        service_snippets_list = []
        domains_map = {d.service_name_slug: d for d in environment.domains}
        for service in deployment_config.services:
            services_info[service.name_slug] = service.model_dump(mode="json")
            service_type_slug = service.service_type.value.lower()

            if service.service_type not in [
                ServiceTypeEnum.BACKEND_API,
                ServiceTypeEnum.BACKEND_WORKER,
                ServiceTypeEnum.FULL_STACK,
            ]:
                continue

            template = self.docker_compose_snippets_env.get_template(
                f"services/{service_type_slug}.yml"
            )
            image_url = images[service.name_slug]

            domain_info = domains_map.get(service.name_slug)
            domain = domain_info.domain_name if domain_info else None

            content = template.render(
                image_name=image_url, port=service.service_port, domain=domain
            )
            service_snippets_list.append(f"# {service.name_slug}\n{content}")
        service_snippets = "\n\n".join(service_snippets_list)

        infra_snippets_list = []
        for infra in deployment_config.infra_deps:
            template = self.docker_compose_snippets_env.get_template(f"{infra.provider}.yml")

            content = template.render(
                version=infra.version,
                app_name=deployment_config.app_name_slug,
                architecture=environment_state.virtual_machine.architecture.value,
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
                environment_state,
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
        print(
            f"\n[bold blue]Setting up container registry for region '{environment.region}'...[/bold"
            " blue]"
        )
        registry_url = self._setup_container_registry(deployment_config, environment)
        images = self._build_and_push_images(deployment_config, environment, registry_url)

        cloud_provider = deployment_config.cloud_provider_instance

        print(f"\n[bold blue]Selecting instance type on {cloud_provider.name()}...[/bold blue]")

        with WaitingSpinner(text="Fetching available instance types", delay=0.1):
            machine_type_list = cloud_provider.get_instance_types(environment.region)

        services_yaml = yaml.dump([s.model_dump(mode="json") for s in deployment_config.services])
        infra_deps_yaml = yaml.dump(
            [i.model_dump(mode="json") for i in deployment_config.infra_deps]
        )
        machine_types_yaml = yaml.dump(machine_type_list.model_dump(mode="json"))

        prompt = MONOLITHIC_MACHINE_REQUIREMENTS_PROMPT_TEMPLATE.format(
            services_yaml=services_yaml,
            infra_deps_yaml=infra_deps_yaml,
            machine_types_yaml=machine_types_yaml,
        )

        with WaitingSpinner(text="Waiting for LLM to select machine types", delay=0.1):
            response = self.agent.run_sync(
                prompt, output_type=MachineTypeList, deps=self.agent_deps
            )

        suggested_machine_types = response.output
        choices, recommended_instance = suggested_machine_types.as_options()

        if not choices:
            raise MonolithicDeploymentError("No suitable instance types found.")

        questions = [
            inquirer.List(
                "instance_type",
                message="Select an instance type for the new environment",
                choices=choices,
                default=recommended_instance,
            )
        ]
        answers = inquirer.prompt(questions)
        selected_machine_type: MachineType = answers["instance_type"]

        instance_type = selected_machine_type.name
        instance_arch = selected_machine_type.architecture
        print(
            f"[bold green]Selected instance type: {instance_type} ({instance_arch.value})[/bold"
            " green]"
        )

        print("\n[bold blue]Creating new virtual machine for monolithic deployment...[/bold blue]")
        instance_public_ip, ansible_user = self._create_virtual_machine(
            deployment_config, environment, instance_type, cloud_provider
        )

        env_state_path = self._get_env_state_path(environment.name)
        env_state = MonolithicDeploymentState(
            registry_url=registry_url,
            virtual_machine=VirtualMachineState(
                ram_gb=selected_machine_type.ram_gb,
                cpu=selected_machine_type.cpu,
                instance_type=instance_type,
                architecture=instance_arch,
                public_ip=instance_public_ip,
                user=ansible_user,
            ),
        )
        env_state.save(env_state_path)
        print(f"Monolithic deployment state saved to {env_state_path}")

        if environment.domains:
            print("\n[bold]Please configure the following DNS records for your domains:[/bold]")
            for domain in environment.domains:
                print("\n[cyan]----------------------------------------[/cyan]")
                print("  [bold]Type:[/bold]  A Record")
                print(f"  [bold]Name:[/bold]  {domain.domain_name}")
                print(f"  [bold]Value:[/bold] {instance_public_ip}")
                print("[cyan]----------------------------------------[/cyan]")

            confirm_question = [
                inquirer.Confirm(
                    "dns_configured",
                    message=(
                        "Have you configured the DNS records as shown above? (This might take a few"
                        " minutes to propagate)"
                    ),
                    default=True,
                )
            ]
            answers = inquirer.prompt(confirm_question)
            if not answers or not answers.get("dns_configured"):
                print("[bold red]DNS configuration not confirmed. Aborting deployment.[/bold red]")
                raise MonolithicDeploymentError("User did not confirm DNS configuration.")

        self._generate_docker_compose(deployment_config, environment, images, env_state)

    def release(
        self,
        deployment_config: DeploymentConfig,
        environment: DeploymentEnvironment,
    ):
        """Deploys the application."""
        env_state_path = self._get_env_state_path(environment.name)
        env_state = MonolithicDeploymentState.load(env_state_path)

        self._build_and_push_images(deployment_config, environment, env_state.registry_url)

        env_file_path = f"/home/{env_state.virtual_machine.user}/app/.env"
        fetched_files = self._fetch_remote_deployment_files(
            environment,
            env_state.virtual_machine.public_ip,
            env_state.virtual_machine.user,
            [env_file_path],
        )

        self._deploy_docker_compose(
            deployment_config,
            environment,
            env_state,
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
            env_state_path = self._get_env_state_path(environment.name)
            env_state = MonolithicDeploymentState.load(env_state_path)
            if not env_state:
                print(
                    f"[bold red]Setup for environment '{environment.name}' is missing or"
                    " incomplete. Cannot proceed with destruction.[/bold red]"
                )
                raise MonolithicDeploymentError(
                    f"Incomplete config for {environment.name}, cannot destroy."
                )

            tf = TerraformProvisioner(working_dir=infra_path)

            variables = {
                "app_name": deployment_config.app_name_slug,
                "instance_type": env_state.virtual_machine.instance_type,
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
