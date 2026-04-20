"""Page-related tools for Plane MCP Server."""

from typing import Any

from fastmcp import FastMCP
from plane.models.pages import CreatePage, Page, UpdatePage

from plane_mcp.client import get_plane_client_context


def _normalize_page_list_response(response: Any) -> list[Page]:
    """Normalize Plane page list responses into a list of Page models."""
    if isinstance(response, list):
        return [Page.model_validate(item) for item in response]

    if isinstance(response, dict):
        results = response.get("results")
        if isinstance(results, list):
            return [Page.model_validate(item) for item in results]

    raise ValueError(f"Unexpected page list response shape: {type(response)!r}")


def register_page_tools(mcp: FastMCP) -> None:
    """Register all page-related tools with the MCP server."""

    @mcp.tool()
    def list_workspace_pages(
        type: str | None = None,
        search: str | None = None,
        per_page: int | None = None,
        cursor: str | None = None,
    ) -> list[Page]:
        """
        List workspace pages.

        Args:
            type: Optional scope filter (all, public, private, shared, archived)
            search: Optional case-insensitive search on page title
            per_page: Optional page size
            cursor: Optional pagination cursor

        Returns:
            List of Page objects
        """
        client, workspace_slug = get_plane_client_context()

        params = {
            "type": type,
            "search": search,
            "per_page": per_page,
            "cursor": cursor,
        }
        response = client.pages._get(
            f"{workspace_slug}/pages",
            params={k: v for k, v in params.items() if v is not None},
        )
        return _normalize_page_list_response(response)

    @mcp.tool()
    def list_project_pages(
        project_id: str,
        type: str | None = None,
        search: str | None = None,
        per_page: int | None = None,
        cursor: str | None = None,
    ) -> list[Page]:
        """
        List project pages.

        Args:
            project_id: UUID of the project
            type: Optional scope filter (all, public, private, shared, archived)
            search: Optional case-insensitive search on page title
            per_page: Optional page size
            cursor: Optional pagination cursor

        Returns:
            List of Page objects
        """
        client, workspace_slug = get_plane_client_context()

        params = {
            "type": type,
            "search": search,
            "per_page": per_page,
            "cursor": cursor,
        }
        response = client.pages._get(
            f"{workspace_slug}/projects/{project_id}/pages",
            params={k: v for k, v in params.items() if v is not None},
        )
        return _normalize_page_list_response(response)

    @mcp.tool()
    def retrieve_workspace_page(
        page_id: str,
    ) -> Page:
        """
        Retrieve a workspace page by ID.

        Args:
            page_id: UUID of the page

        Returns:
            Page object
        """
        client, workspace_slug = get_plane_client_context()

        return client.pages.retrieve_workspace_page(
            workspace_slug=workspace_slug,
            page_id=page_id,
        )

    @mcp.tool()
    def retrieve_project_page(
        project_id: str,
        page_id: str,
    ) -> Page:
        """
        Retrieve a project page by ID.

        Args:
            project_id: UUID of the project
            page_id: UUID of the page

        Returns:
            Page object
        """
        client, workspace_slug = get_plane_client_context()

        return client.pages.retrieve_project_page(
            workspace_slug=workspace_slug,
            project_id=project_id,
            page_id=page_id,
        )

    @mcp.tool()
    def create_workspace_page(
        name: str,
        description_html: str,
        access: int | None = None,
        color: str | None = None,
        is_locked: bool | None = None,
        archived_at: str | None = None,
        view_props: dict[str, Any] | None = None,
        logo_props: dict[str, Any] | None = None,
        external_id: str | None = None,
        external_source: str | None = None,
    ) -> Page:
        """Create a workspace page."""
        client, workspace_slug = get_plane_client_context()

        data = CreatePage(
            name=name,
            description_html=description_html,
            access=access,
            color=color,
            is_locked=is_locked,
            archived_at=archived_at,
            view_props=view_props,
            logo_props=logo_props,
            external_id=external_id,
            external_source=external_source,
        )

        return client.pages.create_workspace_page(
            workspace_slug=workspace_slug,
            data=data,
        )

    @mcp.tool()
    def create_project_page(
        project_id: str,
        name: str,
        description_html: str,
        access: int | None = None,
        color: str | None = None,
        is_locked: bool | None = None,
        archived_at: str | None = None,
        view_props: dict[str, Any] | None = None,
        logo_props: dict[str, Any] | None = None,
        external_id: str | None = None,
        external_source: str | None = None,
    ) -> Page:
        """Create a project page."""
        client, workspace_slug = get_plane_client_context()

        data = CreatePage(
            name=name,
            description_html=description_html,
            access=access,
            color=color,
            is_locked=is_locked,
            archived_at=archived_at,
            view_props=view_props,
            logo_props=logo_props,
            external_id=external_id,
            external_source=external_source,
        )

        return client.pages.create_project_page(
            workspace_slug=workspace_slug,
            project_id=project_id,
            data=data,
        )

    @mcp.tool()
    def update_workspace_page(
        page_id: str,
        name: str | None = None,
        description_html: str | None = None,
        access: int | None = None,
        color: str | None = None,
        is_locked: bool | None = None,
        archived_at: str | None = None,
        view_props: dict[str, Any] | None = None,
        logo_props: dict[str, Any] | None = None,
        external_id: str | None = None,
        external_source: str | None = None,
    ) -> Page:
        """Update a workspace page."""
        client, workspace_slug = get_plane_client_context()

        data = UpdatePage(
            name=name,
            description_html=description_html,
            access=access,
            color=color,
            is_locked=is_locked,
            archived_at=archived_at,
            view_props=view_props,
            logo_props=logo_props,
            external_id=external_id,
            external_source=external_source,
        )

        response = client.pages._patch(
            f"{workspace_slug}/pages/{page_id}",
            data.model_dump(exclude_none=True),
        )
        return Page.model_validate(response)

    @mcp.tool()
    def update_project_page(
        project_id: str,
        page_id: str,
        name: str | None = None,
        description_html: str | None = None,
        access: int | None = None,
        color: str | None = None,
        is_locked: bool | None = None,
        archived_at: str | None = None,
        view_props: dict[str, Any] | None = None,
        logo_props: dict[str, Any] | None = None,
        external_id: str | None = None,
        external_source: str | None = None,
    ) -> Page:
        """Update a project page."""
        client, workspace_slug = get_plane_client_context()

        data = UpdatePage(
            name=name,
            description_html=description_html,
            access=access,
            color=color,
            is_locked=is_locked,
            archived_at=archived_at,
            view_props=view_props,
            logo_props=logo_props,
            external_id=external_id,
            external_source=external_source,
        )

        response = client.pages._patch(
            f"{workspace_slug}/projects/{project_id}/pages/{page_id}",
            data.model_dump(exclude_none=True),
        )
        return Page.model_validate(response)
