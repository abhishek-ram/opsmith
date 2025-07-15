import os
from typing import Annotated, Optional

import inquirer
import logfire
import typer
import yaml
from pydantic import ValidationError
from rich import print

from opsmith.agent import AVAILABLE_MODELS_XREF, ModelConfig, build_agent
from opsmith.cloud_providers import CLOUD_PROVIDER_REGISTRY
from opsmith.cloud_providers.base import CloudCredentialsError
from opsmith.deployment_strategies import DEPLOYMENT_STRATEGY_REGISTRY
from opsmith.repo_map import RepoMap
from opsmith.service_detector import ServiceDetector
from opsmith.spinner import WaitingSpinner
from opsmith.types import (
    DeploymentConfig,
    DeploymentEnvironment,
    InfrastructureDependency,
    ServiceInfo,
)
from opsmith.utils import build_logo, get_missing_external_dependencies

app = typer.Typer()


def _check_external_dependencies():
    """
    Checks if a list of external command-line tools are installed and operational.
    Exits the application if any dependency is not found or non-operational.

    """
    missing_deps = get_missing_external_dependencies(["docker", "terraform"])
    if missing_deps:
        print(
            "[red]Required dependencies not found or not running:[/red] [bold"
            f" red]{', '.join(missing_deps)}[/bold red]"
        )
        print("[red]Please install them and ensure they are in your system's PATH.[/red]")
        raise typer.Exit(code=1)


def parse_model_arg(model: str) -> ModelConfig:
    """
    Fetches the configuration corresponding to the given model name.

    Attempts to retrieve the configuration for the provided model from
    the mapping of available models. If the model name is not found in
    the mapping, an error is raised indicating that the model is unsupported.

    :param model: The name of the model for which the configuration is required.
    :type model: str

    :return: The configuration corresponding to the provided model name.
    :rtype: ModelConfig

    :raises KeyError: If the given model name is not found in the available models mapping.
    :raises typer.BadParameter: If the provided model name is unsupported.
    """
    try:
        return AVAILABLE_MODELS_XREF[model]
    except KeyError:
        raise typer.BadParameter(
            f"Unsupported model name: {model}, must be one of: {AVAILABLE_MODELS_XREF.keys()}"
        )


def api_key_callback(ctx: typer.Context, value: str):
    """
    This function serves as a callback for validating and processing an API key when
    used in conjunction with a command-line interface. The function checks whether
    the mandatory `--model` option is set before associating it with the provided
    API key. If validation passes, it ensures the API key authentication process
    is triggered for the specified model configuration.

    Raises a BadParameter error if `--model` was not supplied before `--api-key`.

    :param ctx: The Typer context object that contains information about the
        current command execution context, including provided options and other
        runtime parameters.
    :type ctx: typer.Context
    :param value: The API key provided by the user via the `--api-key` option
        during the command-line execution.
    :type value: str
    :return: The validated API key after ensuring it is associated with the
        specified model configuration.
    :rtype: str
    """
    if "model" not in ctx.params:
        raise typer.BadParameter("The --model option must be specified before --api-key.")
    model_config = ctx.params["model"]
    model_config.ensure_auth(value)
    return value


@app.callback()
def main(
    ctx: typer.Context,
    model: Annotated[
        ModelConfig,
        typer.Option(
            parser=parse_model_arg,
            help="The LLM model to be used for by the AI Agent.",
        ),
    ],
    api_key: Annotated[
        str,
        typer.Option(
            callback=api_key_callback,
            help=(
                "The API KEY to be used for by the AI Agent. This is the API key for the specified"
                " model."
            ),
        ),
    ],
    logfire_token: Optional[str] = typer.Option(
        default=None,
        help=(
            "Logfire token to be used for logging. If not provided, logs will not be sent to"
            " Logfire."
        ),
    ),
    src_dir: Optional[str] = typer.Option(
        default=None,
        help="Source directory to be used by the command. Defaults to current working directory.",
    ),
    verbose: bool = typer.Option(
        False, "--verbose", "-v", help="Enable verbose output for repo map generation."
    ),
):
    """
    AI Devops engineer in your terminal.
    """
    print(build_logo())

    if logfire_token:
        logfire.configure(token=logfire_token, scrubbing=False)

    ctx.obj = {
        "src_dir": src_dir or os.getcwd(),
        "agent": build_agent(model_config=model, instrument=bool(logfire_token)),
    }

    _check_external_dependencies()


def _validate_service_config(_, config_yaml: str) -> bool:
    try:
        data = yaml.safe_load(config_yaml)
        ServiceInfo(**data)
        return True
    except (yaml.YAMLError, ValidationError) as e:
        print(f"\n[red]>>[/red] Invalid service configuration: {e}\n")
        return False


def _validate_infra_deps_config(_, config_yaml: str) -> bool:
    try:
        if "user_choice" in config_yaml:
            raise ValueError(
                "Provider is 'user_choice'. Please replace it with a valid provider.",
            )

        data = yaml.safe_load(config_yaml)
        if not isinstance(data, list):
            raise ValueError("Configuration must be a YAML list of dependencies.")

        deps = [InfrastructureDependency(**item) for item in data]

        seen_providers = set()
        for dep in deps:
            if dep.provider in seen_providers:
                print("Duplicate provider")
                raise ValueError(
                    f"Duplicate provider found: {dep.provider}. Each provider can only be"
                    " listed once."
                )
            seen_providers.add(dep.provider)
        return True
    except (yaml.YAMLError, ValidationError, ValueError) as e:
        print(f"\n[red]>>[/red] Invalid dependency configuration: {e}\n")
        return False


@app.command()
def setup(ctx: typer.Context):
    """
    Setup the deployment configuration for the repository.
    Identifies services, their languages, types, and frameworks.
    """
    detector = ServiceDetector(src_dir=ctx.obj["src_dir"], agent=ctx.obj["agent"])
    deployment_config = DeploymentConfig.load(ctx.obj["src_dir"])

    current_provider_name = None
    services = []
    infra_deps = []
    scan_services = False
    is_update = bool(deployment_config)
    app_name = None
    environments = []

    if is_update:
        print("\n[bold yellow]Existing deployment configuration found.[/bold yellow]")
        print("\n[bold green]Current Deployment Configuration:[/bold green]")
        print(yaml.dump(deployment_config.model_dump(mode="json")))

        update_actions = ["Re-scan services", "Exit"]
        questions = [
            inquirer.List(
                "action",
                message="What would you like to do?",
                choices=update_actions,
                default="Exit",
            )
        ]
        answers = inquirer.prompt(questions)
        if not answers or answers.get("action") == "Exit":
            print("Exiting setup.")
            return

        if answers.get("action") == "Re-scan services":
            scan_services = True

        # Pre-fill with existing data
        app_name = deployment_config.app_name
        cloud_details = deployment_config.cloud_provider
        services = deployment_config.services
        environments = deployment_config.environments
        infra_deps = deployment_config.infra_deps
    else:
        print("No existing deployment configuration found. Starting analysis...")
        app_name_questions = [
            inquirer.Text("app_name", message="Enter the application name", default=app_name),
        ]
        app_name_answers = inquirer.prompt(app_name_questions)
        if not app_name_answers or not app_name_answers.get("app_name"):
            print("[bold red]Application name is required. Aborting.[/bold red]")
            raise typer.Exit(code=1)
        app_name = app_name_answers["app_name"]

        provider_questions = [
            inquirer.List(
                "cloud_provider",
                message="Select the cloud provider for deployment",
                choices=CLOUD_PROVIDER_REGISTRY.choices,
                default=current_provider_name,
            ),
        ]
        provider_answers = inquirer.prompt(provider_questions)
        if not provider_answers:
            print("[bold red]Cloud provider selection is required. Aborting.[/bold red]")
            raise typer.Exit(code=1)

        selected_provider_value = provider_answers["cloud_provider"]

        # Get cloud details if new or changed
        print(f"Initializing {selected_provider_value} provider...")
        provider_class = CLOUD_PROVIDER_REGISTRY.get_provider_class(selected_provider_value)
        try:
            cloud_details = provider_class.get_account_details().model_dump(mode="json")
        except CloudCredentialsError as e:
            print(f"[bold red]Cloud provider authentication/configuration error:\n{e}[/bold red]")
            raise typer.Exit(code=1)
        except Exception as e:
            print(
                "[bold red]An unexpected error occurred while initializing cloud provider or"
                f" fetching details: {e}. Aborting.[/bold red]"
            )
            raise typer.Exit(code=1)
        scan_services = True

    if scan_services:
        print("Scanning your codebase now to detect services, frameworks, and languages...")
        service_list_obj = detector.detect_services(
            existing_config=deployment_config if is_update else None
        )

        confirmed_services = []

        if service_list_obj.services:
            print("\n[bold]Please review and confirm each detected service:[/bold]")

        for i, service in enumerate(service_list_obj.services):
            service_yaml = yaml.dump(service.model_dump(mode="json"), indent=2)

            editor_prompt_message = (
                f"Review and confirm Service {i + 1}/{len(service_list_obj.services)}"
            )
            questions = [
                inquirer.Editor(
                    "config",
                    message=editor_prompt_message,
                    default=service_yaml,
                    validate=_validate_service_config,
                )
            ]
            answers = inquirer.prompt(questions)
            confirmed_service_data = yaml.safe_load(answers["config"])
            confirmed_service = ServiceInfo(**confirmed_service_data)
            confirmed_services.append(confirmed_service)

            print("\n[bold blue]Generating Dockerfile for the updated service...[/bold blue]")
            detector.generate_dockerfile(service=confirmed_service)

        services = confirmed_services

        infra_deps = service_list_obj.infra_deps
        if infra_deps:
            print("\n[bold]Please review and confirm detected infrastructure dependencies.[/bold]")
            deps_yaml = yaml.dump([dep.model_dump(mode="json") for dep in infra_deps], indent=2)
            editor_prompt_message = (
                "Review and confirm dependencies.\nIf 'provider' is 'user_choice', please replace"
                " it with a valid provider.\nEach provider can only be listed once."
            )
            questions = [
                inquirer.Editor(
                    "config",
                    message=editor_prompt_message,
                    default=deps_yaml,
                    validate=_validate_infra_deps_config,
                )
            ]
            answers = inquirer.prompt(questions)
            confirmed_deps_data = yaml.safe_load(answers["config"])
            infra_deps = [InfrastructureDependency(**data) for data in confirmed_deps_data]

    # Create/Update and Save Configuration
    final_deployment_config = DeploymentConfig(
        app_name=app_name,
        cloud_provider=cloud_details,
        services=services,
        environments=environments,
        infra_deps=infra_deps,
    )
    final_deployment_config.save(ctx.obj["src_dir"])

    if is_update:
        print("\n[bold green]Deployment configuration updated:[/bold green]")
    else:
        print("\n[bold green]Created Deployment Configuration:[/bold green]")
    print(yaml.dump(final_deployment_config.model_dump(mode="json")))


@app.command()
def deploy(ctx: typer.Context):
    """Deploy the application to a specified environment."""
    deployment_config = DeploymentConfig.load(ctx.obj["src_dir"])
    if not deployment_config:
        print(
            "[bold red]No deployment configuration found. Please run 'opsmith setup' first.[/bold"
            " red]"
        )
        raise typer.Exit(code=1)

    choices = deployment_config.environment_names + ["<Create a new environment>"]

    questions = [
        inquirer.List(
            "environment",
            message=(
                "Select a deployment environment or create a new one (Ex: dev, stage, prod, ...)"
            ),
            choices=choices,
        )
    ]

    answers = inquirer.prompt(questions)
    if not answers:
        raise typer.Exit()

    selected_env_name = answers["environment"]

    if selected_env_name == "<Create a new environment>":
        # Get cloud provider to fetch regions
        with WaitingSpinner(text="Fetching regions from your cloud provider", delay=0.1):
            try:
                provider_instance = deployment_config.cloud_provider_instance
                regions = provider_instance.get_regions()
            except CloudCredentialsError as e:
                print(
                    f"[bold red]Cloud provider authentication/configuration error:\n{e}[/bold red]"
                )
                raise typer.Exit(code=1)
            except Exception as e:
                print(
                    "[bold red]An unexpected error occurred while initializing cloud provider or"
                    f" fetching details: {e}. Aborting.[/bold red]"
                )
                raise typer.Exit(code=1)

        new_env_questions = [
            inquirer.Text(
                "env_name",
                message="Enter the new environment name",
                validate=lambda _, x: x.strip() != ""
                and x.strip() not in deployment_config.environment_names
                and x.strip() != "<Create a new environment>",
            ),
            inquirer.List(
                "region",
                message="Select a region for the new environment",
                choices=regions,
            ),
            inquirer.List(
                "strategy",
                message="Select a deployment strategy for the new environment",
                choices=DEPLOYMENT_STRATEGY_REGISTRY.choices,
            ),
        ]
        new_env_answers = inquirer.prompt(new_env_questions)
        if (
            not new_env_answers
            or not new_env_answers.get("env_name")
            or not new_env_answers.get("region")
            or not new_env_answers.get("strategy")
        ):
            print(
                "[bold red]Environment name, region, and strategy are required. Aborting.[/bold"
                " red]"
            )
            raise typer.Exit()

        selected_env_name = new_env_answers["env_name"].strip()
        selected_region = new_env_answers["region"]
        selected_strategy = new_env_answers["strategy"]

        new_env = DeploymentEnvironment(
            name=selected_env_name, region=selected_region, strategy=selected_strategy
        )
        deployment_config.environments.append(new_env)

        deployment_strategy = DEPLOYMENT_STRATEGY_REGISTRY.get_strategy_class(selected_strategy)(
            ctx.obj["agent"],
            ctx.parent.params["src_dir"],
        )
        deployment_strategy.deploy(deployment_config, new_env)

        deployment_config.save(ctx.obj["src_dir"])
        print(
            f"\n[bold green]New environment '{selected_env_name}' in region '{selected_region}'"
            f" with strategy '{selected_strategy}' created and saved.[/bold green]"
        )
        return

    selected_env = deployment_config.get_environment(selected_env_name)

    action_questions = [
        inquirer.List(
            "action",
            message=f"What would you like to do with the '{selected_env_name}' environment?",
            choices=["release", "destroy"],
            default="release",
        )
    ]
    action_answers = inquirer.prompt(action_questions)
    if not action_answers:
        raise typer.Exit()

    selected_action = action_answers["action"]

    deployment_strategy = DEPLOYMENT_STRATEGY_REGISTRY.get_strategy_class(selected_env.strategy)(
        ctx.obj["agent"],
        ctx.parent.params["src_dir"],
    )

    if selected_action == "release":
        deployment_strategy.release(deployment_config, selected_env)
        print(f"\nDeployment to '{selected_env_name}' environment completed.")
    elif selected_action == "destroy":
        deployment_strategy.destroy(deployment_config, selected_env)
        print(f"\nDestruction of '{selected_env_name}' environment completed.")


@app.command()
def repomap(ctx: typer.Context):
    """
    Generates a map of the repository, showing important files and code elements.
    """
    print("Generating repo map now...")
    if ctx.parent.params["src_dir"]:
        current_dir_str = ctx.parent.params["src_dir"]
    else:
        current_dir_str = os.getcwd()

    repo_mapper = RepoMap(
        src_dir=current_dir_str,
        verbose=ctx.parent.params["verbose"],
    )
    repo_map_str = repo_mapper.get_repo_map()

    if repo_map_str:
        typer.echo(repo_map_str)
    else:
        typer.echo("No git-tracked files found in this repository or failed to generate map.")
