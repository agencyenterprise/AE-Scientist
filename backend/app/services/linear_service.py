"""
Linear service for GraphQL API integration.

This module handles communication with Linear's GraphQL API to create
and manage projects from conversations.
"""

import logging
from typing import Any, Dict, NamedTuple, Optional, cast

import aiohttp
from app.config import settings

logger = logging.getLogger(__name__)


class LinearProject(NamedTuple):
    """Linear project creation result."""

    id: str
    name: str
    content: str  # Linear uses content field, not description
    url: str


class LinearService:
    """Service for interacting with Linear GraphQL API."""

    GRAPHQL_URL = "https://api.linear.app/graphql"

    # Hardcoded team key as requested
    TEAM_KEY = "XXX"

    # GraphQL mutation to create a project
    CREATE_PROJECT_MUTATION = """
    mutation CreateProject($input: ProjectCreateInput!) {
        projectCreate(input: $input) {
            success
            project {
                id
                name
                description
                content
                url
                state
                createdAt
            }
        }
    }
    """

    # GraphQL query to get team ID by name
    GET_TEAM_QUERY = """
    query GetTeam($filter: TeamFilter) {
        teams(filter: $filter) {
            nodes {
                id
                name
                key
            }
        }
    }
    """

    def __init__(self) -> None:
        """Initialize the Linear service."""
        if not settings.LINEAR_ACCESS_KEY:
            raise ValueError("LINEAR_ACCESS_KEY environment variable is required")

        self.headers = {
            "Authorization": settings.LINEAR_ACCESS_KEY,
            "Content-Type": "application/json",
        }

    async def _make_graphql_request(
        self, query: str, variables: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Make a GraphQL request to Linear API."""
        payload: Dict[str, Any] = {"query": query}
        if variables:
            payload["variables"] = variables

        async with aiohttp.ClientSession() as session:
            async with session.post(
                self.GRAPHQL_URL, json=payload, headers=self.headers
            ) as response:
                if response.status != 200:
                    error_text = await response.text()
                    raise Exception(
                        f"Linear GraphQL request failed with status {response.status}: {error_text}"
                    )

                result = cast(Dict[str, Any], await response.json())

                if "errors" in result:
                    raise Exception(f"Linear GraphQL errors: {result['errors']}")

                return result

    async def _get_team_id(self) -> str:
        """Get team ID for the hardcoded XXX team."""
        try:
            result = await self._make_graphql_request(self.GET_TEAM_QUERY)

            teams = result["data"]["teams"]["nodes"]

            # Find team by key
            target_team = None
            for team in teams:
                if team["key"].lower() == self.TEAM_KEY.lower():
                    target_team = team
                    break

            if not target_team:
                raise Exception(f"Team with key '{self.TEAM_KEY}' not found in Linear workspace")

            return cast(str, target_team["id"])

        except Exception as e:
            logger.exception(f"Failed to get team ID for key '{self.TEAM_KEY}': {e}")
            raise Exception(f"Failed to get Linear team ID: {str(e)}")

    async def create_project(self, title: str, description: str) -> LinearProject:
        """
        Create a project in Linear.

        Args:
            title: Project title
            description: Project description

        Returns:
            LinearProject with id, name, description, and url

        Raises:
            Exception: If project creation fails
        """
        try:
            logger.info(f"Creating Linear project: {title}")

            # Get team ID
            team_id = await self._get_team_id()
            logger.debug(f"Using team ID: {team_id}")

            # Create project
            result = await self._make_graphql_request(
                self.CREATE_PROJECT_MUTATION,
                variables={
                    "input": {
                        "name": title,
                        "content": description,  # Map our description to Linear's content field
                        "teamIds": [team_id],  # Linear expects array of team IDs
                    }
                },
            )

            project_data = result["data"]["projectCreate"]

            if not project_data["success"]:
                error_msg = project_data.get("error", "Unknown error")
                raise Exception(f"Linear project creation failed: {error_msg}")

            project = project_data["project"]
            linear_project = LinearProject(
                id=project["id"],
                name=project["name"],
                content=project["content"] or "",  # Get Linear's content field
                url=project["url"],
            )

            logger.info("Linear project created successfully")
            logger.info(f"  - ID: {linear_project.id}")
            logger.info(f"  - Name: {linear_project.name}")
            logger.info(f"  - URL: {linear_project.url}")

            return linear_project

        except Exception as e:
            logger.exception(f"Linear project creation failed: {e}")
            raise Exception(f"Failed to create Linear project: {str(e)}")
