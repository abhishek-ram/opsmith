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
{existing_dockerfile_content}

Your task is to generate an optimized and production-ready Dockerfile for this service.
After generating the Dockerfile content, you MUST validate it using the `build_dockerfile` tool.
The `build_dockerfile` tool will first attempt to build the image. If the build is successful,
it will then attempt to run the image.

Analyze the output from `build_dockerfile`:
1.  If the **build fails** (indicated by errors in the build output), revise the Dockerfile
    content based on the error messages and try building again by calling `build_dockerfile`
    with the updated content.
2.  If the **build succeeds but running the image fails**, examine the run output.
    -   If the failure is due to issues like **missing packages, command not found, file not found
        within the container, or incorrect entrypoint/cmd**, revise the Dockerfile to fix these
        issues and call `build_dockerfile` again.
    -   If the failure is due to **missing environment variables, inability to connect to external
        services (like databases or other APIs), port conflicts, or similar runtime configuration
        issues that are not part of the Dockerfile's direct responsibility for package installation
        or command execution**, you can consider the Dockerfile itself valid for this stage.
Repeat this process until the Dockerfile builds successfully and, if it runs, does not fail due to
fixable Dockerfile issues (like missing packages or commands).

Ensure the final Dockerfile:
- Uses an appropriate base image.
- Copies only necessary files.
- Sets up the correct working directory.
- Installs dependencies efficiently.
- Exposes the correct port (if applicable for the service type, e.g., backend-api, frontend, full_stack).
- Defines the correct entrypoint or command.
- Follows Docker best practices (e.g., multi-stage builds if beneficial, non-root user).

Once the Dockerfile is successfully validated (built and, if run, passed the runtime checks for fixable errors)
with the `build_dockerfile` tool, return a `DockerfileContent` object. You MUST populate the
`validation_output` field with the output from the final successful call to the `build_dockerfile`
tool.
If more information is required at any stage, use the `read_file_content` tool.
"""
