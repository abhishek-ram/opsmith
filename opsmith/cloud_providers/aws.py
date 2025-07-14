from typing import Literal, Type

import boto3
import botocore.session
from botocore.exceptions import ClientError, NoCredentialsError
from pydantic import Field

from opsmith.cloud_providers.base import (
    BaseCloudProvider,
    BaseCloudProviderDetail,
    CloudCredentialsError,
    CpuArchitectureEnum,
)


class AWSCloudDetail(BaseCloudProviderDetail):
    name: Literal["AWS"] = Field(default="AWS", description="Provider name, 'AWS'")
    account_id: str = Field(..., description="AWS Account ID.")


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

    def get_instance_type(
        self, cpu: int, ram_gb: int, region: str
    ) -> tuple[str, CpuArchitectureEnum]:
        """
        Retrieves an appropriate instance type for the given resource requirements using heuristics.
        """
        ec2_client = boto3.client("ec2", region_name=region)
        ram_mb = ram_gb * 1024

        # Prioritize newer generation, general-purpose instance families
        instance_families = ["t4g", "t3", "m7g", "m7i", "m6g", "m6i", "m5"]
        instance_type_patterns = [f"{family}.*" for family in instance_families]

        paginator = ec2_client.get_paginator("describe_instance_types")
        pages = paginator.paginate(
            Filters=[
                {"Name": "instance-type", "Values": instance_type_patterns},
                {"Name": "current-generation", "Values": ["true"]},
            ]
        )

        eligible_instances = []
        for page in pages:
            for itype in page["InstanceTypes"]:
                if (
                    "VCpuInfo" in itype
                    and "DefaultVCpus" in itype["VCpuInfo"]
                    and "MemoryInfo" in itype
                    and "SizeInMiB" in itype["MemoryInfo"]
                    and "ProcessorInfo" in itype
                    and "SupportedArchitectures" in itype["ProcessorInfo"]
                    and itype["ProcessorInfo"]["SupportedArchitectures"]
                ):
                    instance_vcpu = itype["VCpuInfo"]["DefaultVCpus"]
                    instance_mem_mb = itype["MemoryInfo"]["SizeInMiB"]
                    instance_arch_str = itype["ProcessorInfo"]["SupportedArchitectures"][0]
                    try:
                        instance_arch = CpuArchitectureEnum(instance_arch_str)
                    except ValueError:
                        continue

                    if instance_vcpu >= cpu and instance_mem_mb >= ram_mb:
                        eligible_instances.append(
                            {
                                "name": itype["InstanceType"],
                                "cpu": instance_vcpu,
                                "ram_mb": instance_mem_mb,
                                "arch": instance_arch,
                            }
                        )

        if not eligible_instances:
            raise ValueError(
                "Could not find any suitable instance type for the given requirements."
            )

        # Sort by vCPU and then RAM to find the smallest/cheapest instance
        eligible_instances.sort(
            key=lambda x: (
                x["cpu"],
                x["ram_mb"],
            )
        )

        selected_instance = eligible_instances[0]
        return selected_instance["name"], selected_instance["arch"]

    @classmethod
    def get_account_details(cls) -> AWSCloudDetail:
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
