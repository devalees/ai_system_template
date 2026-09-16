"""FastAPI routes for Dynamic FastMCP Tool Reflection and Bridge Invocation."""

import uuid
import time
import logging
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, Depends, status, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from core.context import get_active_company_id
from core.mcp_bridge.schemas import (
    MCPToolDefinition,
    MCPToolCallRequest,
    MCPToolCallResponse,
)
from core.mcp_bridge.reflection import mcp_registry

logger = logging.getLogger("sovereign.mcp_bridge.routes")

router = APIRouter(prefix="", tags=["Sovereign FastMCP AI Bridge"])


@router.get(
    "/tools",
    response_model=List[MCPToolDefinition],
    summary="List Reflected FastMCP Tools",
    description="Returns all dynamically reflected FastMCP tools and JSON schemas exposed to Sovereign AI Agents.",
)
async def list_mcp_tools() -> List[MCPToolDefinition]:
    """Retrieve all available FastMCP tools with parameters and metadata."""
    return mcp_registry.list_tools()


@router.post(
    "/execute",
    response_model=MCPToolCallResponse,
    summary="Execute Reflected FastMCP Tool",
    description="Invokes a specific reflected FastMCP tool with validated parameters within active company context.",
)
async def execute_mcp_tool(
    payload: MCPToolCallRequest,
    db: AsyncSession = Depends(get_db),
) -> MCPToolCallResponse:
    """Execute a tool invocation request against backend business engines."""
    start_time = time.time()
    company_id = payload.company_id or get_active_company_id()

    if not company_id:
        # Fallback: if running in dev/standalone test, query first company
        from modules.base.identity_rbac.models import Company
        from sqlalchemy import select
        stmt = select(Company).limit(1)
        company = (await db.execute(stmt)).scalar_one_or_none()
        if company:
            company_id = company.id
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Active company context (X-Company-ID) is required to execute MCP tools.",
            )

    try:
        result = await mcp_registry.execute_tool(
            db=db,
            tool_name=payload.tool,
            arguments=payload.arguments,
            company_id=company_id,
        )
        duration_ms = round((time.time() - start_time) * 1000.0, 2)
        return MCPToolCallResponse(
            tool=payload.tool,
            status="success",
            result=result,
            error=None,
            duration_ms=duration_ms,
        )
    except Exception as exc:
        logger.error(f"Error executing FastMCP tool '{payload.tool}': {exc}", exc_info=True)
        duration_ms = round((time.time() - start_time) * 1000.0, 2)
        return MCPToolCallResponse(
            tool=payload.tool,
            status="error",
            result=None,
            error=str(exc),
            duration_ms=duration_ms,
        )


@router.get(
    "/status",
    summary="FastMCP Bridge Status & AI Modules",
    description="Returns telemetry summary of available MCP tools and list of all ai_enabled modules in the kernel.",
)
async def get_mcp_status() -> Dict[str, Any]:
    """Inspect active FastMCP bridge capabilities."""
    ai_modules = mcp_registry.get_ai_enabled_modules_summary()
    tools = mcp_registry.list_tools()
    return {
        "status": "operational",
        "total_tools": len(tools),
        "tools": [t.name for t in tools],
        "total_ai_enabled_modules": len(ai_modules),
        "ai_enabled_modules": [m["name"] for m in ai_modules],
    }
