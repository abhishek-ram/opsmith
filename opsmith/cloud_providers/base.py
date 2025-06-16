import abc
import enum
from typing import Literal, Union

from pydantic import BaseModel, Field


class CloudProviderEnum(enum.Enum):
    AWS = "AWS"
    GCP = "GCP"


class AWSCloudDetail(BaseModel):
    name: Literal[CloudProviderEnum.AWS.name] = Field(
        default=CloudProviderEnum.AWS.name, description="Provider name, 'aws'"
    )
    account_id: str = Field(..., description="AWS Account ID.")


class GCPCloudDetail(BaseModel):
    name: Literal[CloudProviderEnum.GCP.name] = Field(
        default=CloudProviderEnum.GCP.name, description="Provider name, 'gcp'"
    )
    project_id: str = Field(..., description="GCP Project ID.")


CloudProviderDetail = Union[AWSCloudDetail, GCPCloudDetail]


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

    def __init__(self, *args, **kwargs):
        """
        Initializes the cloud provider.
        Subclasses should implement specific authentication and setup.
        """
        pass

    @abc.abstractmethod
    def get_account_details(self) -> CloudProviderDetail:
        """
        Retrieves structured account details for the cloud provider.
        """
        raise NotImplementedError
