"""
Linear API playground for testing GraphQL project creation.

This script tests the Linear GraphQL API to create projects
before implementing it in the main application.
"""

import asyncio
import os
from typing import Any, Dict, cast

import aiohttp
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

LINEAR_GRAPHQL_URL = "https://api.linear.app/graphql"
LINEAR_ACCESS_KEY = os.getenv("LINEAR_ACCESS_KEY")

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

# GraphQL query to list teams (needed to get team ID for XXX)
GET_TEAMS_QUERY = """
query GetTeams {
    teams {
        nodes {
            id
            name
            key
        }
    }
}
"""


async def get_teams() -> Dict[str, Any]:
    """Get all teams to find the XXX team ID."""
    if not LINEAR_ACCESS_KEY:
        raise ValueError("LINEAR_ACCESS_KEY is required")

    headers = {
        "Authorization": LINEAR_ACCESS_KEY,
        "Content-Type": "application/json",
    }

    payload = {"query": GET_TEAMS_QUERY}

    async with aiohttp.ClientSession() as session:
        async with session.post(LINEAR_GRAPHQL_URL, json=payload, headers=headers) as response:
            if response.status != 200:
                raise Exception(
                    f"GraphQL request failed with status {response.status}: {await response.text()}"
                )

            return cast(Dict[str, Any], await response.json())


async def create_project(team_id: str, name: str, description: str) -> Dict[str, Any]:
    """Create a project in Linear."""
    if not LINEAR_ACCESS_KEY:
        raise ValueError("LINEAR_ACCESS_KEY is required")

    headers = {
        "Authorization": LINEAR_ACCESS_KEY,
        "Content-Type": "application/json",
    }

    # Project input parameters
    project_input = {
        "name": name,
        "content": description,  # Try using content instead of description
        "teamIds": [team_id],  # Linear expects an array of team IDs
    }

    payload = {"query": CREATE_PROJECT_MUTATION, "variables": {"input": project_input}}

    async with aiohttp.ClientSession() as session:
        async with session.post(LINEAR_GRAPHQL_URL, json=payload, headers=headers) as response:
            if response.status != 200:
                raise Exception(
                    f"GraphQL request failed with status {response.status}: {await response.text()}"
                )

            return cast(Dict[str, Any], await response.json())


async def main() -> None:
    """Test Linear project creation."""
    if not LINEAR_ACCESS_KEY:
        print("❌ LINEAR_ACCESS_KEY not found in environment variables")
        return

    try:
        print("🔍 Fetching teams from Linear...")
        teams_response = await get_teams()

        if "errors" in teams_response:
            print(f"❌ GraphQL errors: {teams_response['errors']}")
            return

        teams = teams_response["data"]["teams"]["nodes"]
        print(f"📋 Found {len(teams)} teams:")
        for team in teams:
            print(f"  - {team['name']} (ID: {team['id']}, Key: {team['key']})")

        # Find XXX team by key
        xxx_team = None
        for team in teams:
            if team["key"].lower() == "xxx":
                xxx_team = team
                break

        if not xxx_team:
            print("❌ No teams available!")
            return

        print(f"\n🎯 Using team: {xxx_team['name']} (ID: {xxx_team['id']})")

        # Test project creation
        print("\n🚀 Creating test project...")
        project_response = await create_project(
            team_id=xxx_team["id"],
            name="Test Project from AGI Catalog",
            description="This is a test project created via the Linear GraphQL API from the AGI Judd's Idea Catalog backend.",
        )

        if "errors" in project_response:
            print(f"❌ GraphQL errors: {project_response['errors']}")
            return

        project_data = project_response["data"]["projectCreate"]

        if project_data["success"]:
            project = project_data["project"]
            print("✅ Project created successfully!")
            print(f"📁 Project ID: {project['id']}")
            print(f"📝 Name: {project['name']}")
            print(f"📄 Description: {project.get('description', 'N/A')}")
            print(f"📝 Content: {project.get('content', 'N/A')}")
            print(f"🔗 URL: {project['url']}")
            print(f"📅 Created: {project['createdAt']}")
            print(f"🏷️ State: {project['state']}")

            # This is the data we would store in our database
            print("\n💾 Data to store in database:")
            print(f"  - linear_project_id: {project['id']}")
            print(f"  - title: {project['name']}")
            print(f"  - description: {project.get('description', 'N/A')}")
            print(f"  - content: {project.get('content', 'N/A')}")
            print(f"  - linear_url: {project['url']}")

        else:
            print("❌ Project creation failed: success was false")

    except Exception as e:
        print(f"💥 Error: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
