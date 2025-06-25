import boto3
from botocore.exceptions import ClientError, NoCredentialsError

from opsmith.cloud_providers.base import (
    AWSCloudDetail,
    BaseCloudProvider,
    CloudCredentialsError,
    CloudProviderEnum,
)


class AWSProvider(BaseCloudProvider):
    """AWS cloud provider implementation."""

    def get_account_details(self) -> AWSCloudDetail:
        """
        Retrieves structured AWS account details.
        """
        try:
            sts_client = boto3.client("sts")
            identity = sts_client.get_caller_identity()
            account_id = identity.get("Account")
            if not account_id:
                raise CloudCredentialsError(
                    message=(
                        "AWS account ID could not be determined. This might indicate an issue with"
                        " the credentials or permissions."
                    ),
                    help_url="https://docs.aws.amazon.com/cli/latest/userguide/cli-configure-quickstart.html",
                )
            return AWSCloudDetail(name=CloudProviderEnum.AWS.name, account_id=account_id)
        except (NoCredentialsError, ClientError) as e:
            raise CloudCredentialsError(
                message=f"AWS credentials error: {e}",
                help_url=(
                    "https://docs.aws.amazon.com/cli/latest/userguide/cli-configure-quickstart.html"
                ),
            )
        except Exception as e:
            # Catching other unexpected exceptions during AWS interaction
            raise CloudCredentialsError(
                message=f"An unexpected error occurred while fetching AWS account details: {e}",
                help_url=(
                    "https://docs.aws.amazon.com/cli/latest/userguide/cli-configure-quickstart.html"
                ),
            )
