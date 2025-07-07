from typing import Type

import boto3
import botocore.session
from botocore.exceptions import ClientError, NoCredentialsError

from opsmith.cloud_providers.base import (
    AWSCloudDetail,
    BaseCloudProvider,
    BaseCloudProviderDetail,
    CloudCredentialsError,
)


class AWSProvider(BaseCloudProvider):
    """AWS cloud provider implementation."""

    @classmethod
    def name(cls) -> str:
        """The name of the cloud provider."""
        return "AWS"

    @classmethod
    def description(cls) -> str:
        """A brief description of the cloud provider."""
        return "Amazon Web Services, a comprehensive and broadly adopted cloud platform."

    @classmethod
    def get_detail_model(cls) -> Type[AWSCloudDetail]:
        """The cloud provider detail model."""
        return AWSCloudDetail

    def get_regions(self) -> list[tuple[str, str]]:
        """
        Retrieves a list of available AWS regions with their display names.
        """
        # Get available region codes from EC2
        ec2_client = boto3.client("ec2", region_name="us-east-1")
        response = ec2_client.describe_regions()
        available_region_codes = {region["RegionName"] for region in response["Regions"]}

        # Get region descriptions from botocore's packaged data
        session = botocore.session.get_session()
        # The first partition is 'aws' which contains all standard regions
        region_data = session.get_data("endpoints")["partitions"][0]["regions"]

        regions = []
        for code in available_region_codes:
            data = region_data[code]
            description = data.get("description", code.replace("-", " ").title())
            regions.append((f"{description} ({code})", code))

        return sorted(regions)

    @classmethod
    def get_account_details(cls) -> BaseCloudProviderDetail:
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
            return AWSCloudDetail(account_id=account_id)
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
