from typing import Type

import google.auth
import inquirer
from google.auth.credentials import Credentials
from google.auth.exceptions import DefaultCredentialsError

from opsmith.cloud_providers.base import (
    BaseCloudProvider,
    BaseCloudProviderDetail,
    CloudCredentialsError,
    GCPCloudDetail,
)

GCP_REGION_NAMES = {
    "africa-south1": "Johannesburg",
    "asia-east1": "Taiwan",
    "asia-east2": "Hong Kong",
    "asia-northeast1": "Tokyo",
    "asia-northeast2": "Osaka",
    "asia-northeast3": "Seoul",
    "asia-south1": "Mumbai",
    "asia-south2": "Delhi",
    "asia-southeast1": "Singapore",
    "asia-southeast2": "Jakarta",
    "australia-southeast1": "Sydney",
    "australia-southeast2": "Melbourne",
    "europe-central2": "Warsaw",
    "europe-north1": "Finland",
    "europe-north2": "Kouvola",
    "europe-southwest1": "Madrid",
    "europe-west1": "Belgium",
    "europe-west10": "Berlin",
    "europe-west12": "Turin",
    "europe-west2": "London",
    "europe-west3": "Frankfurt",
    "europe-west4": "Netherlands",
    "europe-west6": "Zurich",
    "europe-west8": "Milan",
    "europe-west9": "Paris",
    "me-central1": "Doha",
    "me-central2": "Dammam",
    "me-west1": "Tel Aviv",
    "northamerica-northeast1": "Montreal",
    "northamerica-northeast2": "Toronto",
    "northamerica-south1": "Queretaro",
    "southamerica-east1": "Sao Paulo",
    "southamerica-west1": "Santiago",
    "us-central1": "Iowa",
    "us-east1": "South Carolina",
    "us-east4": "Northern Virginia",
    "us-east5": "Columbus",
    "us-south1": "Dallas",
    "us-west1": "Oregon",
    "us-west2": "Los Angeles",
    "us-west3": "Salt Lake City",
    "us-west4": "Las Vegas",
}


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
        Retrieves a list of available GCP regions.
        This is a hardcoded list of common regions.
        """
        # GCP doesn't have a simple, unauthenticated API to list all regions.
        # This list includes most of the generally available regions.
        # For an up-to-date list, one could use `gcloud compute regions list`
        # or a more complex API call.
        region_codes = [
            "africa-south1",
            "asia-east1",
            "asia-east2",
            "asia-northeast1",
            "asia-northeast2",
            "asia-northeast3",
            "asia-south1",
            "asia-south2",
            "asia-southeast1",
            "asia-southeast2",
            "australia-southeast1",
            "australia-southeast2",
            "europe-central2",
            "europe-north1",
            "europe-north2",
            "europe-southwest1",
            "europe-west1",
            "europe-west10",
            "europe-west12",
            "europe-west2",
            "europe-west3",
            "europe-west4",
            "europe-west6",
            "europe-west8",
            "europe-west9",
            "me-west1",
            "me-central1",
            "me-central2",
            "northamerica-northeast1",
            "northamerica-northeast2",
            "northamerica-south1",
            "southamerica-east1",
            "southamerica-west1",
            "us-central1",
            "us-east1",
            "us-east4",
            "us-east5",
            "us-south1",
            "us-west1",
            "us-west2",
            "us-west3",
            "us-west4",
        ]

        regions = []
        for code in region_codes:
            name = GCP_REGION_NAMES.get(code, code.replace("-", " ").title())
            regions.append((f"{name} ({code})", code))
        return sorted(regions)

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
