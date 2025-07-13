REPO_ANALYSIS_PROMPT_TEMPLATE = """
You are an expert DevOps engineer. Your task is to analyze the provided repository
and identify all distinct services that need to be deployed.

First, review the repository map provided below to get an overview of the project structure,
key files, and important symbols.

{repo_map_str}

An existing service configuration is provided below.
If the existing configuration is 'N/A', analyze the repository from scratch.
If an existing configuration is provided, review it, and then analyze the current state of the repository.
Your goal is to return a complete, updated configuration that reflects the current state.
- If a service in the existing configuration is no longer present, remove it.
- If a new service has been added, include it.
- If a service's details (language, framework, dependencies, etc.) have changed, update them.
- The final output should be the complete list of services and infrastructure dependencies, not just the changes.

Existing Configuration:
{existing_config_yaml}

Based on this map and the content of relevant files (which you can request using the
'read_file_content' tool), identify the services and a consolidated list of infrastructure
dependencies.

For each service, determine:
1.  `language`: The primary programming language of the service (e.g., "python", "javascript", "java").
2.  `language_version`: The specific version of the language, if identifiable (e.g., "3.9", "17", "ES2020").
3.  `service_type`: The type of the service. Must be one of: "backend_api", "backend_worker", "frontend", "full_stack".
4.  `framework`: The primary framework or library used, if any (e.g., "django", "react", "spring boot", "celery").
5.  `build_tool`: The build tool used for the service, if identifiable (e.g., "maven", "gradle", "npm", "webpack", "pip", "poetry").
6.  `env_vars`: A list of environment variable configurations required by the service. For each variable, specify:
    *   `key`: The name of the environment variable.
    *   `is_secret`: A boolean indicating if the variable should be treated as a secret (e.g., contains API keys, passwords, or other sensitive information).
    *   `default_value`: The default value for the variable, if one is provided in the code.

After identifying all services, create a consolidated list of all unique infrastructure
dependencies (`infra_deps`) across all services. For each dependency, specify:
*   `dependency_type`: The type of the dependency. Must be one of: "database", "cache", "message_queue", "search_engine".
*   `provider`: The specific provider of the dependency. Must be one of: "postgresql", "mysql", "mongodb", "redis", "rabbitmq", "kafka", "elasticsearch", "weaviate", "user_choice".
*   `version`: The version of the dependency, if identifiable.

Return the information as a JSON object containing a list of services and a list of
infrastructure dependencies.
* Read the dependencies list from files like `requirements.txt`, `package.json`, `pom.xml`, `build.gradle`, etc., to get an idea of potential frameworks and infrastructure dependencies.
* Do not rely on the repository map and dependency information alone; read relevant files such as entry points to figure out the services.
* Look for configuration files or code that initializes connections to databases, caches, message queues, or search engines to identify infrastructure dependencies. Consolidate them into a single list.
* If a dependency type is identified (e.g., a database via an ORM like SQLAlchemy or Spring Boot) but the specific provider is configurable or not explicitly set in the code, set the `provider` to `"user_choice"`.
* Scan the code for environment variable usage (e.g., `os.environ.get` in Python, `process.env` in Node.js or settings files) to identify required configurations. Keywords like 'SECRET', 'KEY', 'TOKEN', 'PASSWORD' in the variable name often indicate a secret.
* Read as many files as needed until you are sure about the service and infrastructure dependency details.
"""

DOCKERFILE_GENERATION_PROMPT_TEMPLATE = """
You are an expert DevOps engineer. Your task is to generate a Dockerfile for the
service described below.

Service Details:
{service_info_yaml}

Repository Map:
{repo_map_str}

An existing Dockerfile content is provided below.
If the existing content is 'N/A', analyze the service and repository from scratch to generate a new Dockerfile.
If an existing Dockerfile is provided, review it against the service details and repository map.
Your goal is to return a complete, updated Dockerfile that reflects the current requirements of the service.
- If the existing Dockerfile is still valid and optimal, you should use it.
- If it needs updates (e.g., base image, dependencies, commands), update it.
- The final output should be the complete Dockerfile content, not just the changes.

Existing Dockerfile Content:
```
{existing_dockerfile_content}
```

If `validation_feedback` is provided below, it means the previous attempt to validate the Dockerfile failed.
Use the feedback to correct the Dockerfile.
```
{validation_feedback}
```

Your task is to generate an optimized and production-ready Dockerfile for this service.

Ensure the final Dockerfile:
- Uses an appropriate base image.
- Copies only necessary files.
- Sets up the correct working directory.
- Installs dependencies efficiently.
- Exposes the correct port (if applicable for the service type, e.g., backend-api, frontend, full_stack).
- Defines the correct entrypoint or command.
- Follows Docker best practices (e.g., multi-stage builds if beneficial, non-root user).

If more information is required, use the `read_file_content` tool.
Return a `DockerfileContent` object containing the Dockerfile content.
If you determine that the Dockerfile is correct and any runtime validation errors are
not fixable within the Dockerfile itself (e.g., due to missing environment variables),
set `is_final` to `True` in your response.
"""

MONOLITHIC_MACHINE_REQUIREMENTS_PROMPT_TEMPLATE = """
You are an expert DevOps engineer. Your task is to estimate the resource requirements
for deploying a monolithic application for hobby/experimental purposes.

The application consists of the following services:
{services_yaml}

And has the following infrastructure dependencies:
{infra_deps_yaml}

Based on this information, estimate the smallest possible resources required to run all services
and infrastructure dependencies together on a single machine, prioritizing low cost over performance.
Provide the estimated number of virtual CPU cores and the amount of RAM in gigabytes.

Return the information as a `MachineRequirements` JSON object.
"""

DOCKER_COMPOSE_GENERATION_PROMPT_TEMPLATE = """
You are an expert DevOps engineer. Your task is to generate a complete docker-compose.yml file and its associated environment variables.
You will be provided with a base docker-compose file, snippets for services and infrastructure, and detailed service information.
Your job is to combine these into a single valid docker-compose.yml file and provide all environment variables.

**docker-compose.yml instructions:**
- The `service:` key in service snippets should be replaced by the `service_name_slug`.
- The service snippets are already filled with the correct image names.
- For services of type `BACKEND_API` and `FULL_STACK`, add traefik labels for routing. Use the service name slug as the host rule. e.g. `Host(`{{service_name_slug}}.localhost`)`
- Place all services and infra dependencies under the `services:` key in the final yaml.
- The base file defines a network. All services should be part of this network.
- Each application service should have a `depends_on` section listing all infrastructure dependency services. The service names for infra dependencies are the keys from `infra_snippets`.
- For each application service, add an `environment` section to its definition in `docker-compose.yml`. Use environment variable references, e.g. `VAR_NAME=${{VAR_NAME}}`.

**Environment and Secrets instructions:**
- For infrastructure service snippets that use placeholders like `${{VAR}}`, you must generate a secure value for `VAR`. Use the `generate_secret` tool to create secure passwords or other secret values.
- For each application service, you must determine its environment variables. Use the `env_vars` from `Service Info` as a base. Do not change the variable names (`key`).
- You must deduce values for variables where possible. For example, if a service needs a database URL and there is a `postgresql` infrastructure dependency, construct the correct connection string (e.g., `postgresql://user:password@postgresql:5432/dbname`). The service name in the docker network will be the key from `infra_snippets` (e.g., `postgresql`).
- Return the complete content for a `.env` file in the `env_file_content` field. The content should be a string with each variable on a new line, in `KEY="VALUE"` format.

Base docker-compose:
{base_compose}

Service Info (service_name_slug: service_details):
{services_info_yaml}

Service snippets (service_name_slug: snippet):
{service_snippets}

Infrastructure dependency snippets (provider_name: snippet):
{infra_snippets}
"""
