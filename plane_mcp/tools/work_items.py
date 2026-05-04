"""Work item-related tools for Plane MCP Server."""

from typing import Any, get_args

from fastmcp import FastMCP
from plane.models.enums import PriorityEnum
from plane.models.query_params import PaginatedQueryParams, RetrieveQueryParams, WorkItemQueryParams
from plane.models.work_items import (
    AdvancedSearchResult,
    AdvancedSearchWorkItem,
    CreateWorkItem,
    PaginatedWorkItemResponse,
    UpdateWorkItem,
    WorkItem,
    WorkItemDetail,
    WorkItemSearch,
)

from plane_mcp.client import get_plane_client_context


def _build_advanced_search_filters(
    *,
    assignee_ids: list[str] | None = None,
    state_ids: list[str] | None = None,
    state_groups: list[str] | None = None,
    priorities: list[str] | None = None,
    label_ids: list[str] | None = None,
    type_ids: list[str] | None = None,
    cycle_ids: list[str] | None = None,
    module_ids: list[str] | None = None,
    is_archived: bool | None = None,
    created_by_ids: list[str] | None = None,
) -> dict[str, Any] | None:
    """Build an AND filter dict from flat filter params."""
    conditions: list[dict[str, Any]] = []
    if assignee_ids:
        conditions.append({"assignee_id__in": assignee_ids})
    if state_ids:
        conditions.append({"state_id__in": state_ids})
    if state_groups:
        conditions.append({"state_group__in": state_groups})
    if priorities:
        conditions.append({"priority__in": priorities})
    if label_ids:
        conditions.append({"label_id__in": label_ids})
    if type_ids:
        conditions.append({"type_id__in": type_ids})
    if cycle_ids:
        conditions.append({"cycle_id__in": cycle_ids})
    if module_ids:
        conditions.append({"module_id__in": module_ids})
    if is_archived is not None:
        conditions.append({"is_archived": is_archived})
    if created_by_ids:
        conditions.append({"created_by_id__in": created_by_ids})
    if not conditions:
        return None
    if len(conditions) == 1:
        return conditions[0]
    return {"and": conditions}


def _can_filter_work_items_locally(
    *,
    assignee_ids: list[str] | None,
    label_ids: list[str] | None,
    type_ids: list[str] | None,
    cycle_ids: list[str] | None,
    module_ids: list[str] | None,
    workspace_search: bool,
) -> bool:
    """Use normal list endpoints for filters the MCP server can safely emulate."""
    return bool(
        not assignee_ids
        and not label_ids
        and not type_ids
        and not cycle_ids
        and not module_ids
    )


def _state_id(value: Any) -> str | None:
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        state_id = value.get("id")
        return state_id if isinstance(state_id, str) else None
    return getattr(value, "id", None)


def _matches_work_item_query(item: WorkItem, query: str | None) -> bool:
    if not query:
        return True

    needle = query.strip().lower()
    if not needle:
        return True

    haystack = " ".join(
        str(value or "").lower()
        for value in (
            getattr(item, "name", None),
            getattr(item, "description_stripped", None),
            getattr(item, "description_html", None),
            getattr(item, "external_id", None),
        )
    )
    return needle in haystack


def _list_project_work_items(
    *,
    client: Any,
    workspace_slug: str,
    project_id: str,
    cursor: str | None,
    expand: str | None,
    fields: str | None,
    order_by: str | None,
    external_id: str | None,
    external_source: str | None,
) -> list[WorkItem]:
    all_items: list[WorkItem] = []
    next_cursor = cursor
    while True:
        params = WorkItemQueryParams(
            cursor=next_cursor,
            per_page=100,
            expand=expand,
            fields=fields,
            order_by=order_by,
            external_id=external_id,
            external_source=external_source,
        )
        response: PaginatedWorkItemResponse = client.work_items.list(
            workspace_slug=workspace_slug,
            project_id=project_id,
            params=params,
        )
        if not response.results:
            break
        all_items.extend(response.results)
        if not response.next_page_results:
            break
        next_cursor = response.next_cursor
        if not next_cursor:
            break
    return all_items


def _list_workspace_project_ids(*, client: Any, workspace_slug: str) -> list[str]:
    project_ids: list[str] = []
    next_cursor: str | None = None
    while True:
        params = PaginatedQueryParams(cursor=next_cursor, per_page=100)
        response = client.projects.list(workspace_slug=workspace_slug, params=params)
        for project in response.results:
            project_id = getattr(project, "id", None)
            if project_id:
                project_ids.append(project_id)
        if not response.next_page_results:
            break
        next_cursor = response.next_cursor
        if not next_cursor:
            break
    return project_ids


def _filter_project_work_items_locally(
    items: list[WorkItem],
    *,
    query: str | None,
    state_ids: list[str] | None,
    state_groups: list[str] | None,
    state_groups_by_id: dict[str, str],
    priorities: list[str] | None,
    is_archived: bool | None,
    created_by_ids: list[str] | None,
    limit: int | None,
) -> list[WorkItem]:
    filtered: list[WorkItem] = []
    for item in items:
        if not _matches_work_item_query(item, query):
            continue
        item_state_id = _state_id(getattr(item, "state", None))
        if state_ids and item_state_id not in state_ids:
            continue
        if state_groups and state_groups_by_id.get(item_state_id or "") not in state_groups:
            continue
        if priorities and getattr(item, "priority", None) not in priorities:
            continue
        if is_archived is not None and bool(getattr(item, "archived_at", None)) != is_archived:
            continue
        if created_by_ids and getattr(item, "created_by", None) not in created_by_ids:
            continue
        filtered.append(item)
        if limit is not None and len(filtered) >= limit:
            break
    return filtered


def register_work_item_tools(mcp: FastMCP) -> None:
    """Register all work item-related tools with the MCP server."""

    @mcp.tool()
    def list_work_items(
        project_id: str | None = None,
        query: str | None = None,
        assignee_ids: list[str] | None = None,
        state_ids: list[str] | None = None,
        state_groups: list[str] | None = None,
        priorities: list[str] | None = None,
        label_ids: list[str] | None = None,
        type_ids: list[str] | None = None,
        cycle_ids: list[str] | None = None,
        module_ids: list[str] | None = None,
        is_archived: bool | None = None,
        created_by_ids: list[str] | None = None,
        workspace_search: bool = False,
        limit: int | None = None,
        cursor: str | None = None,
        per_page: int | None = None,
        expand: str | None = None,
        fields: str | None = None,
        order_by: str | None = None,
        external_id: str | None = None,
        external_source: str | None = None,
    ) -> list[WorkItem] | list[AdvancedSearchResult]:
        """
        List work items in a project or search across the workspace.

        Query, state, priority, archived, and creator filters use normal list
        endpoints with local filtering so API-key/service-account clients do not
        need Plane's privileged advanced-search API. Unsupported filters still use
        advanced search.

        Args:
            project_id: UUID of the project. Required when no filters are provided.
                Optional when using filters (omit for workspace-wide search).
            query: Free-form text search across work item name and description
            assignee_ids: List of user UUIDs to filter by assignee
            state_ids: List of state UUIDs to filter by state
            state_groups: List of state groups to filter by
                (backlog, unstarted, started, completed, cancelled)
            priorities: List of priority values to filter by
                (urgent, high, medium, low, none)
            label_ids: List of label UUIDs to filter by label
            type_ids: List of work item type UUIDs to filter by type
            cycle_ids: List of cycle UUIDs to filter by cycle
            module_ids: List of module UUIDs to filter by module
            is_archived: Filter by archived status (true/false)
            created_by_ids: List of user UUIDs to filter by creator
            workspace_search: When true, search across all projects in the workspace.
                Only used with filters. Defaults to false.
            limit: Maximum number of results (only used with filters, default 25)
            cursor: Pagination cursor for getting next set of results (list only)
            per_page: Number of results per page, 1-100 (list only)
            expand: Comma-separated list of related fields to expand in response
                (list only, e.g. "assignees,labels,state")
            fields: Comma-separated list of fields to include in response (list only)
            order_by: Field to order results by, prefix with '-' for descending (list only)
            external_id: External system identifier for filtering (list only)
            external_source: External system source name for filtering (list only)

        Returns:
            List of WorkItem objects (unfiltered) or AdvancedSearchResult objects (filtered)
        """
        client, workspace_slug = get_plane_client_context()

        filters = _build_advanced_search_filters(
            assignee_ids=assignee_ids,
            state_ids=state_ids,
            state_groups=state_groups,
            priorities=priorities,
            label_ids=label_ids,
            type_ids=type_ids,
            cycle_ids=cycle_ids,
            module_ids=module_ids,
            is_archived=is_archived,
            created_by_ids=created_by_ids,
        )

        if (filters is not None or query is not None) and _can_filter_work_items_locally(
            assignee_ids=assignee_ids,
            label_ids=label_ids,
            type_ids=type_ids,
            cycle_ids=cycle_ids,
            module_ids=module_ids,
            workspace_search=workspace_search,
        ):
            project_ids = [project_id] if project_id else _list_workspace_project_ids(
                client=client,
                workspace_slug=workspace_slug,
            )
            filtered_items: list[WorkItem] = []
            for current_project_id in project_ids:
                state_groups_by_id: dict[str, str] = {}
                if state_groups:
                    states_response = client.states.list(
                        workspace_slug=workspace_slug,
                        project_id=current_project_id,
                    )
                    state_groups_by_id = {state.id: state.group for state in states_response.results}

                all_items = _list_project_work_items(
                    client=client,
                    workspace_slug=workspace_slug,
                    project_id=current_project_id,
                    cursor=cursor if project_id else None,
                    expand=expand,
                    fields=fields,
                    order_by=order_by,
                    external_id=external_id,
                    external_source=external_source,
                )
                filtered_items.extend(
                    _filter_project_work_items_locally(
                        all_items,
                        query=query,
                        state_ids=state_ids,
                        state_groups=state_groups,
                        state_groups_by_id=state_groups_by_id,
                        priorities=priorities,
                        is_archived=is_archived,
                        created_by_ids=created_by_ids,
                        limit=None,
                    )
                )
                if limit is not None and len(filtered_items) >= limit:
                    return filtered_items[:limit]

            return filtered_items[:limit] if limit is not None else filtered_items

        if filters is not None or query is not None:
            data = AdvancedSearchWorkItem(
                query=query,
                filters=filters,
                limit=limit,
                project_id=project_id,
                workspace_search=workspace_search or None,
            )
            return client.work_items.advanced_search(
                workspace_slug=workspace_slug,
                data=data,
            )

        if project_id is None:
            raise ValueError("project_id is required when no filters are provided")

        params = WorkItemQueryParams(
            cursor=cursor,
            per_page=per_page,
            expand=expand,
            fields=fields,
            order_by=order_by,
            external_id=external_id,
            external_source=external_source,
        )

        response: PaginatedWorkItemResponse = client.work_items.list(
            workspace_slug=workspace_slug,
            project_id=project_id,
            params=params,
        )

        return response.results

    @mcp.tool()
    def create_work_item(
        project_id: str,
        name: str,
        assignees: list[str] | None = None,
        labels: list[str] | None = None,
        type_id: str | None = None,
        point: int | None = None,
        description_html: str | None = None,
        description_stripped: str | None = None,
        priority: str | None = None,
        start_date: str | None = None,
        target_date: str | None = None,
        sort_order: float | None = None,
        is_draft: bool | None = None,
        external_source: str | None = None,
        external_id: str | None = None,
        parent: str | None = None,
        state: str | None = None,
        estimate_point: str | None = None,
        type: str | None = None,
    ) -> WorkItem:
        """
        Create a new work item.

        Args:
            workspace_slug: The workspace slug identifier
            project_id: UUID of the project
            name: Work item name (required)
            assignees: List of user IDs to assign to the work item
            labels: List of label IDs to attach to the work item
            type_id: UUID of the work item type
            point: Story point value
            description_html: HTML description of the work item
            description_stripped: Plain text description (stripped of HTML)
            priority: Priority level (urgent, high, medium, low, none)
            start_date: Start date (ISO 8601 format)
            target_date: Target/end date (ISO 8601 format)
            sort_order: Sort order value
            is_draft: Whether the work item is a draft
            external_source: External system source name
            external_id: External system identifier
            parent: UUID of the parent work item
            state: UUID of the state
            estimate_point: Estimate point value
            type: Work item type identifier

        Returns:
            Created WorkItem object
        """
        client, workspace_slug = get_plane_client_context()

        # Validate priority against allowed literal values
        validated_priority: PriorityEnum | None = (
            priority if priority in get_args(PriorityEnum) else None  # type: ignore[assignment]
        )

        data = CreateWorkItem(
            name=name,
            assignees=assignees,
            labels=labels,
            type_id=type_id,
            point=point,
            description_html=description_html,
            description_stripped=description_stripped,
            priority=validated_priority,
            start_date=start_date,
            target_date=target_date,
            sort_order=sort_order,
            is_draft=is_draft,
            external_source=external_source,
            external_id=external_id,
            parent=parent,
            state=state,
            estimate_point=estimate_point,
            type=type,
        )

        return client.work_items.create(workspace_slug=workspace_slug, project_id=project_id, data=data)

    @mcp.tool()
    def retrieve_work_item(
        project_id: str,
        work_item_id: str,
        expand: str | None = None,
        fields: str | None = None,
        external_id: str | None = None,
        external_source: str | None = None,
        order_by: str | None = None,
    ) -> WorkItemDetail:
        """
        Retrieve a work item by ID.

        Args:
            workspace_slug: The workspace slug identifier
            project_id: UUID of the project
            work_item_id: UUID of the work item
            expand: Comma-separated fields to expand (e.g., "assignees,labels,state")
            fields: Comma-separated fields to include in response
            external_id: External system identifier for filtering
            external_source: External system source name for filtering
            order_by: Field to order results by (typically not used for single item retrieval)

        Returns:
            WorkItemDetail object with expanded relationships
        """
        client, workspace_slug = get_plane_client_context()

        params = RetrieveQueryParams(
            expand=expand,
            fields=fields,
            external_id=external_id,
            external_source=external_source,
            order_by=order_by,
        )

        return client.work_items.retrieve(
            workspace_slug=workspace_slug,
            project_id=project_id,
            work_item_id=work_item_id,
            params=params,
        )

    @mcp.tool()
    def retrieve_work_item_by_identifier(
        project_identifier: str,
        issue_identifier: int,
        expand: str | None = None,
        fields: str | None = None,
        external_id: str | None = None,
        external_source: str | None = None,
        order_by: str | None = None,
    ) -> WorkItemDetail:
        """
        Retrieve a work item by project identifier and issue sequence number.

        Args:
            workspace_slug: The workspace slug identifier
            project_identifier: Project identifier string (e.g., "MP" for "My Project")
            issue_identifier: Issue sequence number (e.g., 1, 2, 3)
            expand: Comma-separated fields to expand (e.g., "assignees,labels,state")
            fields: Comma-separated list of fields to include in response
            external_id: External system identifier for filtering
            external_source: External system source name for filtering
            order_by: Field to order results by (typically not used for single item retrieval)

        Returns:
            WorkItemDetail object with expanded relationships
        """
        client, workspace_slug = get_plane_client_context()

        params = RetrieveQueryParams(
            expand=expand,
            fields=fields,
            external_id=external_id,
            external_source=external_source,
            order_by=order_by,
        )

        return client.work_items.retrieve_by_identifier(
            workspace_slug=workspace_slug,
            project_identifier=project_identifier,
            issue_identifier=issue_identifier,
            params=params,
        )

    @mcp.tool()
    def update_work_item(
        project_id: str,
        work_item_id: str,
        name: str | None = None,
        assignees: list[str] | None = None,
        labels: list[str] | None = None,
        type_id: str | None = None,
        point: int | None = None,
        description_html: str | None = None,
        description_stripped: str | None = None,
        priority: str | None = None,
        start_date: str | None = None,
        target_date: str | None = None,
        sort_order: float | None = None,
        is_draft: bool | None = None,
        external_source: str | None = None,
        external_id: str | None = None,
        parent: str | None = None,
        state: str | None = None,
        estimate_point: str | None = None,
        type: str | None = None,
    ) -> WorkItem:
        """
        Update a work item by ID.

        Args:
            workspace_slug: The workspace slug identifier
            project_id: UUID of the project
            work_item_id: UUID of the work item
            name: Work item name
            assignees: List of user IDs to assign to the work item
            labels: List of label IDs to attach to the work item
            type_id: UUID of the work item type
            point: Story point value
            description_html: HTML description of the work item
            description_stripped: Plain text description (stripped of HTML)
            priority: Priority level (urgent, high, medium, low, none)
            start_date: Start date (ISO 8601 format)
            target_date: Target/end date (ISO 8601 format)
            sort_order: Sort order value
            is_draft: Whether the work item is a draft
            external_source: External system source name
            external_id: External system identifier
            parent: UUID of the parent work item
            state: UUID of the state
            estimate_point: Estimate point value
            type: Work item type identifier

        Returns:
            Updated WorkItem object
        """
        client, workspace_slug = get_plane_client_context()

        # Validate priority against allowed literal values
        validated_priority: PriorityEnum | None = (
            priority if priority in get_args(PriorityEnum) else None  # type: ignore[assignment]
        )

        data = UpdateWorkItem(
            name=name,
            assignees=assignees,
            labels=labels,
            type_id=type_id,
            point=point,
            description_html=description_html,
            description_stripped=description_stripped,
            priority=validated_priority,
            start_date=start_date,
            target_date=target_date,
            sort_order=sort_order,
            is_draft=is_draft,
            external_source=external_source,
            external_id=external_id,
            parent=parent,
            state=state,
            estimate_point=estimate_point,
            type=type,
        )

        return client.work_items.update(
            workspace_slug=workspace_slug,
            project_id=project_id,
            work_item_id=work_item_id,
            data=data,
        )

    @mcp.tool()
    def delete_work_item(project_id: str, work_item_id: str) -> None:
        """
        Delete a work item by ID.

        Args:
            workspace_slug: The workspace slug identifier
            project_id: UUID of the project
            work_item_id: UUID of the work item
        """
        client, workspace_slug = get_plane_client_context()
        client.work_items.delete(workspace_slug=workspace_slug, project_id=project_id, work_item_id=work_item_id)

    @mcp.tool()
    def search_work_items(
        query: str,
        expand: str | None = None,
        fields: str | None = None,
        external_id: str | None = None,
        external_source: str | None = None,
        order_by: str | None = None,
    ) -> WorkItemSearch:
        """
        Search work items across a workspace.

        Args:
            workspace_slug: The workspace slug identifier
            query: This is a free-form text search and will be used to search the work items
                    by name, description etc.
            expand: Comma-separated list of related fields to expand in response
            fields: Comma-separated list of fields to include in response
            external_id: External system identifier for filtering
            external_source: External system source name for filtering
            order_by: Field to order results by. Prefix with '-' for descending order

        Returns:
            WorkItemSearch object containing search results
        """
        client, workspace_slug = get_plane_client_context()

        params = RetrieveQueryParams(
            expand=expand,
            fields=fields,
            external_id=external_id,
            external_source=external_source,
            order_by=order_by,
        )

        return client.work_items.search(workspace_slug=workspace_slug, query=query, params=params)
