"""Tool centre business logic."""

from typing import List

from ai import tools
from common.exception_handler import CustomException
from common.result import PageInfo
from models import FunctionTool, ToolCallLog


def tool_dict(tool: FunctionTool) -> dict:
    return {
        "id": tool.id,
        "tool_code": tool.tool_code,
        "tool_name": tool.tool_name,
        "description": tool.description,
        "input_schema": tool.input_schema,
        "enabled": tool.enabled,
        "sort": tool.sort,
        # It's got tools on it, but not in the code.
        # Otherwise, the manager thinks it's working. The model doesn't actually get it.
        "implemented": tool.tool_code in tools.IMPLEMENTATIONS,
        "create_time": tool.create_time,
        "update_time": tool.update_time,
    }


def _validate(payload: dict) -> None:
    if not payload.get("tool_code"):
        raise CustomException("Please enter tool encoding")
    if not payload.get("tool_name"):
        raise CustomException("Please enter the tool name")
    # The description will be sent to the model as it is, and the model will determine when to adjust the tool.
    if not payload.get("description"):
        raise CustomException("Please enter a tool description by which the model will determine when to call this tool.")


async def add(payload: dict) -> None:
    _validate(payload)
    if await FunctionTool.get_or_none(tool_code=payload["tool_code"]):
        raise CustomException("Tool Encoding Repeated")
    await FunctionTool.create(
        tool_code=payload["tool_code"],
        tool_name=payload["tool_name"],
        description=payload.get("description"),
        input_schema=payload.get("input_schema"),
        enabled=payload.get("enabled") or "Yes",
        sort=payload.get("sort") or 0,
    )


async def update(tool_id: int | None, payload: dict) -> None:
    if tool_id is None:
        raise CustomException("Tool ID cannot be empty")
    if await FunctionTool.get_or_none(id=tool_id) is None:
        raise CustomException("No tools found")
    _validate(payload)
    if await FunctionTool.filter(tool_code=payload["tool_code"]).exclude(id=tool_id).exists():
        raise CustomException("Tool Encoding Repeated")
    await FunctionTool.filter(id=tool_id).update(
        tool_code=payload["tool_code"],
        tool_name=payload["tool_name"],
        description=payload.get("description"),
        input_schema=payload.get("input_schema"),
        enabled=payload.get("enabled") or "Yes",
        sort=payload.get("sort") or 0,
    )


async def toggle(tool_id: int, enabled: str) -> None:
    """Enables the switch on the page. The next implementation of the modified model will not be available for this tool."""
    if enabled not in {"Yes", "No"}:
        raise CustomException("Error enabling status parameter")
    if await FunctionTool.get_or_none(id=tool_id) is None:
        raise CustomException("No tools found")
    await FunctionTool.filter(id=tool_id).update(enabled=enabled)


async def delete(tool_id: int) -> None:
    tool = await FunctionTool.get_or_none(id=tool_id)
    if tool is None:
        raise CustomException("No tools found")
    # Once the tools in the code are removed, the model can never adjust to it and is easily forgotten.
    if tool.tool_code in tools.IMPLEMENTATIONS:
        raise CustomException("The tools in the code that are realized are not allowed to be deleted. Please use disablement")
    await FunctionTool.filter(id=tool_id).delete()


async def select_page(keyword: str = "", enabled: str = "", page_num: int = 1, page_size: int = 10) -> PageInfo:
    query = FunctionTool.filter(tool_name__contains=keyword)
    if enabled:
        query = query.filter(enabled=enabled)
    items = await query.order_by("sort", "id").offset((page_num - 1) * page_size).limit(page_size)
    total = await query.count()
    return PageInfo(total=total, list=[tool_dict(item) for item in items])


async def preview_definitions() -> List[dict]:
    """Preview the actual tool definition that will be sent to the model.

    This JSON section is shown on the page, and the manager can see what the model will receive immediately after changing the description.
    """
    enabled_tools = await tools.load_enabled_tools()
    return tools.to_openai_tools(enabled_tools)


async def select_logs(
    tool_code: str = "",
    call_status: str = "",
    run_id: int | None = None,
    page_num: int = 1,
    page_size: int = 10,
) -> PageInfo:
    query = ToolCallLog.all()
    if tool_code:
        query = query.filter(tool_code=tool_code)
    if call_status:
        query = query.filter(call_status=call_status)
    if run_id:
        query = query.filter(run_id=run_id)
    logs = await query.order_by("-id").offset((page_num - 1) * page_size).limit(page_size)
    total = await query.count()
    return PageInfo(
        total=total,
        list=[
            {
                "id": log.id,
                "run_id": log.run_id,
                "step_id": log.step_id,
                "tool_code": log.tool_code,
                "tool_name": log.tool_name,
                "request_params": log.request_params,
                "response_result": log.response_result,
                "call_status": log.call_status,
                "error_message": log.error_message,
                "cost_millis": log.cost_millis,
                "create_time": log.create_time,
            }
            for log in logs
        ],
    )


async def log_summary() -> List[dict]:
    """The number and success rate of calls by tool shows which tools are most commonly used and which is the most vulnerable to failure."""
    all_tools = await FunctionTool.all().order_by("sort", "id")
    summary = []
    for tool in all_tools:
        total = await ToolCallLog.filter(tool_code=tool.tool_code).count()
        failed = await ToolCallLog.filter(tool_code=tool.tool_code, call_status="Failed").count()
        summary.append(
            {
                "tool_code": tool.tool_code,
                "tool_name": tool.tool_name,
                "enabled": tool.enabled,
                "total": total,
                "failed": failed,
                # None of the obsolete success rates were shown as empty, not 100%.
                "success_rate": round((total - failed) / total * 100, 1) if total else None,
            }
        )
    return summary
