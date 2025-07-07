from opsmith.cloud_providers.aws import AWSProvider
from opsmith.cloud_providers.base import CloudProviderRegistry
from opsmith.cloud_providers.gcp import GCPProvider

CLOUD_PROVIDER_REGISTRY = CloudProviderRegistry()

CLOUD_PROVIDER_REGISTRY.register(AWSProvider)
CLOUD_PROVIDER_REGISTRY.register(GCPProvider)

# Load any providers from installed packages
CLOUD_PROVIDER_REGISTRY.load_providers_from_entry_points()
