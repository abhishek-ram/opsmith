import google.auth
import inquirer
from google.auth.credentials import Credentials
from google.auth.exceptions import DefaultCredentialsError

from opsmith.cloud_providers import CloudProviderEnum
from opsmith.cloud_providers.base import (
    BaseCloudProvider,
    CloudCredentialsError,
    GCPCloudDetail,
)


class GCPProvider(BaseCloudProvider):
    """GCP cloud provider implementation."""

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

    def get_account_details(self) -> GCPCloudDetail:
        """
        Retrieves structured GCP account details by listing available projects
        and prompting the user for selection.
        """
        try:
            self.get_credentials()

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
            return GCPCloudDetail(name=CloudProviderEnum.GCP.name, project_id=selected_project_id)

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
