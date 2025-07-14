from typing import Type

import google.auth
import inquirer
from google.auth.credentials import Credentials
from google.auth.exceptions import DefaultCredentialsError
from google.cloud import compute_v1

from opsmith.cloud_providers.base import (
    BaseCloudProvider,
    BaseCloudProviderDetail,
    CloudCredentialsError,
    CpuArchitectureEnum,
    GCPCloudDetail,
)


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
            # The description is often more user-friendly than the name
            name = region.description or region.name.replace("-", " ").title()
            code = region.name
            regions.append((f"{name} ({code})", code))

        return sorted(regions)

    def get_instance_type(
        self, cpu: int, ram_gb: int, region: str
    ) -> tuple[str, CpuArchitectureEnum]:
        """
        Retrieves an appropriate instance type for the given resource requirements using the GCP API.
        """
        client = compute_v1.MachineTypesClient(credentials=self.get_credentials())
        project_id = self.provider_detail.project_id
        ram_mb = ram_gb * 1024

        # We need a zone to list machine types. We'll pick a zone in the region, assuming standard naming.
        zone = f"{region}-a"

        request = compute_v1.ListMachineTypesRequest(project=project_id, zone=zone)
        pager = client.list(request=request)

        eligible_machines = []
        for mtype in pager:
            if mtype.deprecated:
                continue

            # Filter for general-purpose, newer generation instance families
            arch = CpuArchitectureEnum.X86_64
            # Adding arm64 (t2a) support to be consistent with AWS provider
            if mtype.name.startswith(("t2a-", "c4a-")):
                arch = CpuArchitectureEnum.ARM64

            if mtype.guest_cpus >= cpu and mtype.memory_mb >= ram_mb:
                eligible_machines.append(
                    {
                        "name": mtype.name,
                        "cpu": mtype.guest_cpus,
                        "ram_mb": mtype.memory_mb,
                        "arch": arch,
                    }
                )

        if not eligible_machines:
            raise ValueError(
                "Could not find any suitable instance type for the given requirements in zone"
                f" {zone}."
            )

        # Sort by vCPU, then RAM to find the smallest/cheapest instance
        eligible_machines.sort(key=lambda x: (x["cpu"], x["ram_mb"]))

        selected_machine = eligible_machines[0]
        return selected_machine["name"], selected_machine["arch"]

    @classmethod
    def get_account_details(cls) -> BaseCloudProviderDetail:
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
