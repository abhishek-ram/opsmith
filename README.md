# Opsmith: An AI devops engineer in your terminal

Opsmith is a command-line tool that acts as an AI-powered DevOps assistant. It's designed to streamline the process of deploying your applications to the cloud, from analyzing your codebase to provisioning infrastructure and deploying your services.

Opsmith helps you with the following tasks:

- **Codebase Analysis**: It scans your repository to automatically detect services, programming languages, frameworks, and infrastructure dependencies (like databases or caches).
- **Configuration Generation**: Based on its analysis, Opsmith generates necessary deployment artifacts.
- **Infrastructure Provisioning**: It uses tools like Terraform and Ansible to provision and configure required cloud resources on supported providers (e.g., AWS, GCP).
- **Deployment**: It handles the deployment of your application using various strategies, such as a monolithic deployment on a single virtual machine for hobby projects.

The primary goal of Opsmith is to make cloud deployments accessible to all developers, regardless of their DevOps expertise. It achieves this by automating complex tasks through an interactive setup process, allowing you to focus on writing code. Opsmith is also designed to prevent cloud provider lock-in, which helps control long-term costs. The generated configurations are standard and maintainable, making it easy to hand over the deployment to an in-house DevOps team.
