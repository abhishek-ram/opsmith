# Opsmith: An AI devops engineer in your terminal

Opsmith is a command-line tool that acts as an AI-powered DevOps assistant. It's designed to streamline the process of deploying your applications to the cloud, from analyzing your codebase to provisioning infrastructure and deploying your services.

Opsmith helps you with the following tasks:

- **Codebase Analysis**: It scans your repository to automatically detect services, programming languages, frameworks, and infrastructure dependencies (like databases or caches).
- **Configuration Generation**: Based on its analysis, Opsmith generates necessary deployment artifacts.
- **Infrastructure Provisioning**: It uses tools like Terraform and Ansible to provision and configure required cloud resources on supported providers (e.g., AWS, GCP).
- **Deployment**: It handles the deployment of your application using various strategies, such as a monolithic deployment on a single virtual machine for hobby projects.

The primary goal of Opsmith is to make cloud deployments accessible to all developers, regardless of their DevOps expertise. It achieves this by automating complex tasks through an interactive setup process, allowing you to focus on writing code. Opsmith is also designed to prevent cloud provider lock-in, which helps control long-term costs. The generated configurations are standard and maintainable, making it easy to hand over the deployment to an in-house DevOps team.

## Table of Contents

- [Getting Started](#getting-started)
  - [Installation](#installation)
  - [Deployment Workflow](#deployment-workflow)



## Getting Started

### Installation

1.  **Prerequisites**: Opsmith requires `Docker` and `Terraform` to be installed and available in your system's `PATH`.

    -   **macOS (with [Homebrew](https://brew.sh/))**:
        ```shell
        brew install --cask docker
        brew install terraform
        ```
        After installation, make sure you start Docker Desktop.

    -   **Windows (with [Chocolatey](https://chocolatey.org/))**:
        ```shell
        choco install docker-desktop terraform
        ```
        After installation, make sure you start Docker Desktop.

    -   **Linux (Debian/Ubuntu)**:
        Please follow the official installation guides for [Docker](https://docs.docker.com/engine/install/ubuntu/) and [Terraform](https://developer.hashicorp.com/terraform/install).

2.  **Install Opsmith**:
    Once the prerequisites are installed, you can install Opsmith using `pip`:
    ```shell
    pip install opsmith-cli
    ```

### Deployment Workflow

Deploying your application with Opsmith follows a straightforward workflow:

1.  **Setup Your Project**

    Navigate to your project's root directory, which should be a Git repository, and run the `setup` command. This command initializes your deployment configuration by analyzing your codebase to detect services and infrastructure requirements.

    ```shell
    opsmith --model <your-llm-provider:model-name> --api-key <your-api-key> setup
    ```

    You will be prompted to:
    -   Provide an application name.
    -   Select a cloud provider (e.g., AWS, GCP).
    -   Review and confirm the services and infrastructure dependencies detected by the AI.
    -   Opsmith will then generate a `Dockerfile` for each of your services.

2.  **Deploy Your Application**

    After setting up the configuration, deploy your application using the `deploy` command:

    ```shell
    opsmith --model <your-llm-provider:model-name> --api-key <your-api-key> deploy
    ```

    This will guide you through:
    -   Creating a new deployment environment (e.g., `dev`, `staging`, `production`).
    -   Selecting a cloud region.
    -   Choosing a deployment strategy (e.g., `Monolithic`).
    -   Configuring domain names for your services if needed.

    Opsmith will then provision all the necessary cloud infrastructure and deploy your application.

3.  **Manage Your Deployments**

    To manage an existing environment, run the `deploy` command again. You can select an environment and perform the following actions:
    -   `release`: Deploy a new version of your application.
    -   `run`: Execute a command on a specific service within your environment (e.g., run database migrations).
    -   `delete`: Tear down all the infrastructure and delete the environment.
