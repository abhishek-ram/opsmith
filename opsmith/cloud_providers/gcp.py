from typing import Literal, Type

import google.auth
import inquirer
from google.auth.credentials import Credentials
from google.auth.exceptions import DefaultCredentialsError
from google.cloud import compute_v1
from pydantic import Field

from opsmith.cloud_providers.base import (
    BaseCloudProvider,
    BaseCloudProviderDetail,
    CloudCredentialsError,
    CpuArchitectureEnum,
    MachineType,
    MachineTypeList,
)

GCP_REGION_DESCRIPTIONS = {
    "africa-south1": "Johannesburg, South Africa",
    "asia-east1": "Changhua County, Taiwan",
    "asia-east2": "Hong Kong",
    "asia-northeast1": "Tokyo, Japan",
    "asia-northeast2": "Osaka, Japan",
    "asia-northeast3": "Seoul, South Korea",
    "asia-south1": "Mumbai, India",
    "asia-south2": "Delhi, India",
    "asia-southeast1": "Jurong West, Singapore",
    "asia-southeast2": "Jakarta, Indonesia",
    "australia-southeast1": "Sydney, Australia",
    "australia-southeast2": "Melbourne, Australia",
    "europe-central2": "Warsaw, Poland",
    "europe-north1": "Hamina, Finland",
    "europe-southwest1": "Madrid, Spain",
    "europe-west1": "St. Ghislain, Belgium",
    "europe-west2": "London, UK",
    "europe-west3": "Frankfurt, Germany",
    "europe-west4": "Eemshaven, Netherlands",
    "europe-west6": "Zürich, Switzerland",
    "europe-west8": "Milan, Italy",
    "europe-west9": "Paris, France",
    "europe-west12": "Turin, Italy",
    "israel-central1": "Tel Aviv, Israel",
    "me-central1": "Doha, Qatar",
    "me-west1": "Tel Aviv, Israel",
    "northamerica-northeast1": "Montréal, Québec, Canada",
    "northamerica-northeast2": "Toronto, Ontario, Canada",
    "southamerica-east1": "São Paulo, Brazil",
    "southamerica-west1": "Santiago, Chile",
    "us-central1": "Council Bluffs, Iowa, USA",
    "us-east1": "Moncks Corner, South Carolina, USA",
    "us-east4": "Ashburn, Virginia, USA",
    "us-east5": "Columbus, Ohio, USA",
    "us-south1": "Dallas, Texas, USA",
    "us-west1": "The Dalles, Oregon, USA",
    "us-west2": "Los Angeles, California, USA",
    "us-west3": "Salt Lake City, Utah, USA",
    "us-west4": "Las Vegas, Nevada, USA",
}


class GCPCloudDetail(BaseCloudProviderDetail):
    name: Literal["GCP"] = Field(default="GCP", description="Provider name, 'GCP'")
    project_id: str = Field(..., description="GCP Project ID.")


class GCPProvider(BaseCloudProvider):
    """GCP cloud provider implementation."""

    @classmethod
    def name(cls) -> str:
        """The name of the cloud provider."""
        return "GCP"

    @classmethod
    def description(cls) -> str:
        """A brief description of the cloud provider."""
        return "Google Cloud Platform, a suite of cloud computing services from Google."

    @classmethod
    def get_detail_model(cls) -> Type[GCPCloudDetail]:
        """The cloud provider detail model."""
        return GCPCloudDetail

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._credentials = None

    def get_credentials(self) -> Credentials:
        """
        Provides the functionality to retrieve cached credentials or obtain default
        Google credentials if none are available.

        :raises google.auth.exceptions.GoogleAuthError: If authentication fails or
           valid credentials could not be obtained.
        :rtype: google.auth.credentials.Credentials
        :return: Returns the cached credentials if available, otherwise retrieves
           and returns the default credentials via Google's authentication library.
        """
        if not self._credentials:
            self._credentials, _ = google.auth.default()
        return self._credentials

    def get_regions(self) -> list[tuple[str, str]]:
        """
        Retrieves a list of available GCP regions using the GCP API.
        """
        client = compute_v1.RegionsClient(credentials=self.get_credentials())
        project_id = self.provider_detail.project_id

        request = compute_v1.ListRegionsRequest(project=project_id)
        pager = client.list(request=request)

        regions = []
        for region in pager:
            code = region.name
            name = (
                GCP_REGION_DESCRIPTIONS.get(code)
                or region.description
                or code.replace("-", " ").title()
            )
            regions.append((f"{name} ({code})", code))

        return sorted(regions, key=lambda x: x[1])

    def get_instance_types(self, region: str) -> MachineTypeList:
        """
        Retrieves a list of available instance types for the given region using the GCP API.
        """
        client = compute_v1.MachineTypesClient(credentials=self.get_credentials())
        project_id = self.provider_detail.project_id

        # We need a zone to list machine types. We'll pick a zone in the region, assuming standard naming.
        zone = f"{region}-a"

        request = compute_v1.ListMachineTypesRequest(project=project_id, zone=zone)
        pager = client.list(request=request)

        all_machines = []
        for mtype in pager:
            if mtype.deprecated:
                continue

            # Filter for general-purpose, newer generation instance families
            arch = CpuArchitectureEnum.X86_64
            # Adding arm64 (t2a) support to be consistent with AWS provider
            if mtype.name.startswith(("t2a-", "c4a-")):
                arch = CpuArchitectureEnum.ARM64

            all_machines.append(
                MachineType(
                    name=mtype.name,
                    cpu=mtype.guest_cpus,
                    ram_gb=round(mtype.memory_mb / 1024, 2),
                    architecture=arch,
                )
            )

        if not all_machines:
            raise ValueError(f"Could not find any instance types in zone {zone}.")

        return MachineTypeList(machines=all_machines)

    @classmethod
    def get_account_details(cls) -> GCPCloudDetail:
        """
        Retrieves structured GCP account details by listing available projects
        and prompting the user for selection.
        """
        try:
            credentials, _ = google.auth.default()

            questions = [
                inquirer.Text(
                    name="project_id",
                    message="Enter the GCP project you want to use",
                ),
            ]

            answers = inquirer.prompt(questions)
            if not answers or not answers.get("project_id"):
                raise ValueError("GCP project selection is required. Aborting.")

            selected_project_id = answers["project_id"]
            return GCPCloudDetail(project_id=selected_project_id)

        except DefaultCredentialsError as e:
            raise CloudCredentialsError(
                message=f"GCP Application Default Credentials error: {e}",
                help_url="https://cloud.google.com/docs/authentication/provide-credentials-adc",
            )
        except Exception as e:
            raise CloudCredentialsError(
                message=f"An unexpected error occurred while fetching GCP project list: {e}",
                help_url="https://cloud.google.com/docs/authentication/provide-credentials-adc",
            )
