from typing import Dict, Type

from .aws import AWSProvider
from .base import BaseCloudProvider, CloudProviderEnum
from .gcp import GCPProvider

CLOUD_PROVIDER_REGISTRY: Dict[CloudProviderEnum, Type[BaseCloudProvider]] = {
    CloudProviderEnum.AWS: AWSProvider,
    CloudProviderEnum.GCP: GCPProvider,
}
