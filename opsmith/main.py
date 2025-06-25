import os
from typing import Annotated, Optional

import inquirer
import logfire
import typer
import yaml
from rich import print

from opsmith.agent import AVAILABLE_MODELS_XREF, ModelConfig
from opsmith.cloud_providers import CLOUD_PROVIDER_REGISTRY
from opsmith.cloud_providers.base import CloudCredentialsError, CloudProviderEnum
from opsmith.deployer import Deployer, DeploymentConfig  # Import the new Deployer class
from opsmith.repo_map import RepoMap

app = typer.Typer()


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
    if logfire_token:
        logfire.configure(token=logfire_token, scrubbing=False)
    ctx.obj = {
        "deployer": Deployer(
            src_dir=src_dir or os.getcwd(),
            model_config=model,
            verbose=verbose,
            instrument=bool(logfire_token),
        )
    }


@app.command()
def setup(ctx: typer.Context):
    """
    Setup the deployment configuration for the repository.
    Identifies services, their languages, types, and frameworks.
    """
    deployer = ctx.obj["deployer"]
    deployment_config = deployer.get_deployment_config()

    cloud_details = None
    current_provider_name = None
    services = []
    services_updated = False
    is_update = bool(deployment_config)
    app_name = None

    if is_update:
        print("\n[bold yellow]Existing deployment configuration found.[/bold yellow]")
        print("\n[bold green]Current Deployment Configuration:[/bold green]")
        print(yaml.dump(deployment_config.model_dump(mode="json")))

        update_answers = inquirer.prompt(
            [
                inquirer.Confirm(
                    "update", message="Do you want to update the configuration?", default=True
                )
            ]
        )
        if not update_answers or not update_answers.get("update"):
            print("Skipping configuration update.")
            return

        # Pre-fill with existing data
        app_name = deployment_config.app_name
        cloud_details = deployment_config.cloud_provider
        current_provider_name = deployment_config.cloud_provider.name
        services = deployment_config.services
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

    # Cloud Provider Selection
    provider_questions = [
        inquirer.List(
            "cloud_provider",
            message="Select the cloud provider for deployment",
            choices=[provider.value for provider in CloudProviderEnum],
            default=current_provider_name,
        ),
    ]
    provider_answers = inquirer.prompt(provider_questions)
    if not provider_answers:
        print("[bold red]Cloud provider selection is required. Aborting.[/bold red]")
        raise typer.Exit(code=1)

    selected_provider_value = provider_answers["cloud_provider"]
    selected_provider_enum = CloudProviderEnum(selected_provider_value)

    # Get cloud details if new or changed
    if not is_update or selected_provider_enum.name != current_provider_name:
        print(f"Initializing {selected_provider_enum.name} provider...")
        provider_class = CLOUD_PROVIDER_REGISTRY[selected_provider_enum]
        try:
            provider_instance = provider_class()
            cloud_details = provider_instance.get_account_details()
        except CloudCredentialsError as e:
            print(f"[bold red]Cloud provider authentication/configuration error:\n{e}[/bold red]")
            raise typer.Exit(code=1)
        except Exception as e:
            print(
                "[bold red]An unexpected error occurred while initializing cloud provider or"
                f" fetching details: {e}. Aborting.[/bold red]"
            )
            raise typer.Exit(code=1)

    # Service Detection
    if is_update:
        service_questions = [
            inquirer.Confirm(
                "update_services", message="Do you want to re-scan for services?", default=False
            )
        ]
        service_answers = inquirer.prompt(service_questions)
        if service_answers and service_answers.get("update_services"):
            services_updated = True
    else:  # New config, so we must scan
        services_updated = True

    if services_updated:
        print("Scanning your codebase now to detect services, frameworks, and languages...")
        service_list_obj = deployer.detect_services()
        services = service_list_obj.services

    # Create/Update and Save Configuration
    final_deployment_config = DeploymentConfig(
        app_name=app_name,
        cloud_provider=cloud_details,
        services=services,
    )
    deployer.save_deployment_config(final_deployment_config)

    if is_update:
        print("\n[bold green]Deployment configuration updated:[/bold green]")
    else:
        print("\n[bold green]Created Deployment Configuration:[/bold green]")
    print(yaml.dump(final_deployment_config.model_dump(mode="json")))

    # Generate Dockerfiles if services were changed
    if services_updated:
        print("\n[bold blue]Services were updated. Generating Dockerfiles...[/bold blue]")
        deployer.generate_dockerfiles()


@app.command()
def deploy(ctx: typer.Context):
    """"""
    pass


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
