import abc
from importlib.metadata import entry_points
from typing import Any, Dict, List, Literal, Optional, Tuple, Type, Union

from pydantic import BaseModel, Field, TypeAdapter
from rich import print


class BaseCloudProviderDetail(BaseModel):
    name: str = Field(..., description="Provider name")


class CloudProviderRegistry:
    """A singleton registry for cloud providers."""

    _instance: Optional["CloudProviderRegistry"] = None
    _providers: Dict[str, Type["BaseCloudProvider"]]
    _detail_models: List[Type["BaseCloudProviderDetail"]]

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._providers = {}
            cls._instance._detail_models = []
        return cls._instance

    def register(self, provider_class: Type["BaseCloudProvider"]):
        """Registers a cloud provider."""
        # Not raising error on overwrite allows for easy extension/replacement
        self._providers[provider_class.name()] = provider_class
        self._detail_models.append(provider_class.get_detail_model())

    def get_provider_class(self, provider_name: str) -> Type["BaseCloudProvider"]:
        """Retrieves a provider class from the registry."""
        if provider_name not in self._providers:
            raise ValueError(f"Provider '{provider_name}' not found.")
        return self._providers[provider_name]

    @property
    def choices(self) -> List[Tuple[str, str]]:
        """Returns a list of (display text, value) tuples for use in prompts."""
        choices_list = []
        for name, provider_class in sorted(self._providers.items()):
            display_text = f"{name} - {provider_class.description()}"
            choices_list.append((display_text, name))
        return choices_list

    @property
    def detail_models_union(self) -> Any:
        """Returns a Union of all registered cloud provider detail models."""
        if not self._detail_models:
            # This case should ideally not happen in normal operation
            # as built-in providers are registered.
            return type(None)
        return Union[tuple(self._detail_models)]

    def load_providers_from_entry_points(self):
        """Loads providers from 'opsmith.cloud_providers' entry points."""
        discovered_entry_points = entry_points(group="opsmith.cloud_providers")

        for entry_point in discovered_entry_points:
            try:
                provider_class = entry_point.load()
                self.register(provider_class)
                print(f"Loaded cloud provider: {provider_class.name()}")
            except Exception as e:
                print(
                    "[yellow]Warning: Failed to load cloud provider from entry point"
                    f" '{entry_point.name}': {e}[/yellow]"
                )


class AWSCloudDetail(BaseCloudProviderDetail):
    name: Literal["AWS"] = Field(default="AWS", description="Provider name, 'AWS'")
    account_id: str = Field(..., description="AWS Account ID.")


class GCPCloudDetail(BaseCloudProviderDetail):
    name: Literal["GCP"] = Field(default="GCP", description="Provider name, 'GCP'")
    project_id: str = Field(..., description="GCP Project ID.")


class CloudCredentialsError(Exception):
    """Custom exception for cloud credential errors."""

    def __init__(self, message: str, help_url: str):
        self.message = message
        self.help_url = help_url
        super().__init__(
            f"{self.message}\nPlease ensure your credentials are set up correctly. For more"
            f" information, visit: {self.help_url}"
        )


class BaseCloudProvider(abc.ABC):
    """Abstract base class for cloud providers."""

    @classmethod
    @abc.abstractmethod
    def name(cls) -> str:
        """The name of the cloud provider."""
        raise NotImplementedError

    @classmethod
    @abc.abstractmethod
    def description(cls) -> str:
        """A brief description of the cloud provider."""
        raise NotImplementedError

    @classmethod
    @abc.abstractmethod
    def get_detail_model(cls) -> Type["BaseCloudProviderDetail"]:
        """The cloud provider detail model."""
        raise NotImplementedError

    @classmethod
    @abc.abstractmethod
    def get_account_details(cls) -> "BaseCloudProviderDetail":
        """
        Retrieves structured account details for the cloud provider.
        """
        raise NotImplementedError

    def __init__(self, provider_detail: dict, *args, **kwargs):
        """
        Initializes the cloud provider.
        Subclasses should implement specific authentication and setup.
        """
        self.provider_detail = TypeAdapter(self.get_detail_model()).validate_python(provider_detail)

    @abc.abstractmethod
    def get_regions(self) -> List[Tuple[str, str]]:
        """
        Retrieves a list of available regions for the cloud provider.
        Returns a list of tuples, where each tuple contains the display name and the region code.
        """
        raise NotImplementedError
