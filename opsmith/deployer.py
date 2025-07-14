import subprocess
import tempfile
import uuid
from pathlib import Path
from typing import Optional

import yaml
from rich import print

from opsmith.agent import AgentDeps, ModelConfig, build_agent
from opsmith.prompts import (
    DOCKERFILE_GENERATION_PROMPT_TEMPLATE,
    REPO_ANALYSIS_PROMPT_TEMPLATE,
)
from opsmith.repo_map import RepoMap
from opsmith.settings import settings
from opsmith.spinner import WaitingSpinner
from opsmith.types import DockerfileContent, ServiceInfo, ServiceList, ServiceTypeEnum

MAX_DOCKERFILE_GENERATE_ATTEMPTS = 5


class Deployer:
    def __init__(
        self,
        src_dir: str,
        model_config: ModelConfig,
        verbose: bool = False,
        instrument: bool = False,
    ):
        self.deployments_path = Path(src_dir).joinpath(settings.deployments_dir)
        self.agent_deps = AgentDeps(src_dir=Path(src_dir))
        self.agent = build_agent(model_config=model_config, instrument=instrument)
        self.repo_map = RepoMap(
            src_dir=src_dir,
            verbose=verbose,
        )
        self.verbose = verbose

    def generate_dockerfile(self, service: ServiceInfo):
        """Generates Dockerfiles for each service in the deployment configuration."""
        buildable_service_types = [
            ServiceTypeEnum.BACKEND_API,
            ServiceTypeEnum.FULL_STACK,
            ServiceTypeEnum.BACKEND_WORKER,
        ]
        if service.service_type not in buildable_service_types:
            print(
                f"\n[bold yellow]Dockerfile not needed for service {service.service_type},"
                " skipping.[/bold yellow]"
            )
            return

        service_name_slug = f"{service.language}_{service.service_type.value}".replace(
            " ", "_"
        ).lower()
        service_dir_name = "images"
        service_dir_path = self.deployments_path / service_dir_name / service_name_slug
        service_dir_path.mkdir(parents=True, exist_ok=True)
        dockerfile_path_abs = service_dir_path / "Dockerfile"
        print(
            "\n[bold]Generating Dockerfile for service:"
            f" {service.language} ({service.service_type})...[/bold]"
        )

        existing_dockerfile_content = "N/A"
        if dockerfile_path_abs.exists():
            with open(dockerfile_path_abs, "r", encoding="utf-8") as f:
                existing_dockerfile_content = f.read()

        service_info_yaml = yaml.dump(service.model_dump(mode="json"), indent=2)
        validation_feedback = ""
        dockerfile_content = ""
        messages = []

        for attempt in range(MAX_DOCKERFILE_GENERATE_ATTEMPTS):
            print(f"\n[bold]Attempt {attempt + 1}/{MAX_DOCKERFILE_GENERATE_ATTEMPTS}...[/bold]")
            prompt = DOCKERFILE_GENERATION_PROMPT_TEMPLATE.format(
                service_info_yaml=service_info_yaml,
                repo_map_str=self.repo_map.get_repo_map(),
                existing_dockerfile_content=existing_dockerfile_content,
                validation_feedback=validation_feedback,
            )
            with WaitingSpinner(text="Waiting for the LLM to generate the Dockerfile", delay=0.1):
                response = self.agent.run_sync(
                    prompt,
                    deps=self.agent_deps,
                    output_type=DockerfileContent,
                    message_history=messages,
                )
                dockerfile_content = response.output.content
                is_final = response.output.is_final
                messages = response.new_messages()

            with WaitingSpinner(text="Validating generated Dockerfile", delay=0.1):
                validation_error = self._validate_dockerfile(dockerfile_content)

            if validation_error is None:
                print("[bold green]Dockerfile validation successful.[/bold green]")
                with open(dockerfile_path_abs, "w", encoding="utf-8") as f:
                    f.write(dockerfile_content)
                print(f"[green]Dockerfile saved to: {dockerfile_path_abs}[/green]")
                return

            # Only trust is_final if there was feedback provided to the LLM (i.e. not first attempt)
            if is_final and validation_feedback:
                print(
                    "[bold yellow]Dockerfile validation failed, but LLM marked it as final."
                    " Accepting.[/bold yellow]"
                )
                with open(dockerfile_path_abs, "w", encoding="utf-8") as f:
                    f.write(dockerfile_content)
                print(f"[green]Dockerfile saved to: {dockerfile_path_abs}[/green]")
                return

            print("[bold red]Dockerfile validation failed.[/bold red]")
            validation_feedback = validation_error

        raise Exception(
            "Failed to generate a valid Dockerfile after"
            f" {MAX_DOCKERFILE_GENERATE_ATTEMPTS} attempts."
        )

    def _validate_dockerfile(self, dockerfile_content: str) -> Optional[str]:
        """
        Validates a Dockerfile by building and running it.
        Returns an error message string on failure, None on success.
        """
        repo_root = self.agent_deps.src_dir.resolve()
        image_tag = f"opsmith-build-test-{uuid.uuid4()}"

        try:
            # Create temporary directory for Dockerfile
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_dockerfile = Path(temp_dir) / "Dockerfile"
                # Write Dockerfile content
                with open(temp_dockerfile, "w", encoding="utf-8") as f:
                    f.write(dockerfile_content)

                # Execute docker build command
                print("[bold blue]Attempting to build the Dockerfile...[/bold blue]")
                build_process = subprocess.run(
                    [
                        "docker",
                        "build",
                        "-f",
                        str(temp_dockerfile),
                        "-t",
                        image_tag,
                        str(repo_root),
                    ],
                    capture_output=True,
                    text=True,
                )
                build_output_str = (
                    f"Build Output (stdout):\n{build_process.stdout}\nBuild Output"
                    f" (stderr):\n{build_process.stderr}"
                )

                if build_process.returncode != 0:
                    # Build failed
                    return (
                        "Dockerfile build failed. Please analyze the following output and revise"
                        f" the Dockerfile:\n{build_output_str}"
                    )

            # Build successful, now try to run the image
            # Using --rm to automatically remove the container when it exits.
            print("[bold blue]Build successful. Attempting to run the container...[/bold blue]")
            run_process = subprocess.run(
                [
                    "docker",
                    "run",
                    "--rm",
                    image_tag,
                ],
                capture_output=True,
                text=True,
                timeout=30,  # Timeout for the run command to prevent indefinite hangs
            )
            run_output_str = (
                f"Run Output (stdout):\n{run_process.stdout}\nRun Output"
                f" (stderr):\n{run_process.stderr}"
            )

            if run_process.returncode != 0:
                # Run failed.
                return (
                    "Dockerfile built successfully, but running the image failed. Please analyze"
                    " the following run output and revise the Dockerfile to fix issues like"
                    " missing packages or command errors. If you believe the Dockerfile is"
                    " correct and the failure is due to runtime issues (e.g. missing environment"
                    " variables), then return the Dockerfile content again but set `is_final` to"
                    " true in the `DockerfileValidationResponse`.\n\nRun"
                    f" Output:\n{run_output_str}\n\nOriginal Build Output"
                    f" was:\n{build_output_str}"
                )
        except subprocess.TimeoutExpired:
            print(
                "[bold yellow]Running the Docker image timed out. This could mean the service is"
                " running. Considering Dockerfile as valid.[/bold yellow]"
            )
            return None  # Success for our purpose
        finally:
            # Clean up image
            cleanup_image_process = subprocess.run(
                ["docker", "rmi", "-f", image_tag], capture_output=True, text=True
            )
            if (
                cleanup_image_process.returncode != 0
                and "no such image" not in cleanup_image_process.stderr.lower()
            ):
                print(
                    f"Warning: Failed to remove Docker image {image_tag}:"
                    f" {cleanup_image_process.stderr.strip()}"
                )
        return None

    def detect_services(self, existing_config: Optional[ServiceList] = None) -> ServiceList:
        """
        Scans the repository to determine the services to be deployed, using the AI agent.

        Generates a repository map, then uses an AI agent with a file reading tool
        to identify services and their characteristics.

        Returns:
            A ServiceList object detailing the services to be deployed.
        """
        repo_map_str = self.repo_map.get_repo_map()
        if self.verbose:
            print("Repo map generated:")

        if existing_config:
            existing_config_yaml = yaml.dump(existing_config.model_dump(mode="json"), indent=2)
        else:
            existing_config_yaml = "N/A"

        prompt = REPO_ANALYSIS_PROMPT_TEMPLATE.format(
            repo_map_str=repo_map_str, existing_config_yaml=existing_config_yaml
        )

        print("Calling AI agent to analyse the repo and determine the services...")
        with WaitingSpinner(text="Waiting for the LLM", delay=0.1):
            run_result = self.agent.run_sync(prompt, output_type=ServiceList, deps=self.agent_deps)

        return run_result.output
