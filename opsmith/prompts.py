REPO_ANALYSIS_PROMPT_TEMPLATE = """
You are an expert DevOps engineer. Your task is to analyze the provided repository
and identify all distinct services that need to be deployed.

First, review the repository map provided below to get an overview of the project structure,
key files, and important symbols.

{repo_map_str}

Based on this map and the content of relevant files (which you can request using the
'read_file_content' tool), identify the services. For each service, determine:
1.  `language`: The primary programming language of the service (e.g., "python", "javascript", "java").
2.  `language_version`: The specific version of the language, if identifiable (e.g., "3.9", "17", "ES2020").
3.  `service_type`: The type of the service. Must be one of: "backend-api", "backend-worker", "frontend", "full_stack".
4.  `framework`: The primary framework or library used, if any (e.g., "django", "react", "spring boot", "celery").
5.  `build_tool`: The build tool used for the service, if identifiable (e.g., "maven", "gradle", "npm", "webpack", "pip", "poetry").

Return the information as a list of services.
* Read the dependencies list to get an idea of potential frameworks.
* Do not come to a conclusion just with this information, consider the repo structure to read the potential entry point files.
* Read as many files as needed to be sure about the service type and framework.
"""
