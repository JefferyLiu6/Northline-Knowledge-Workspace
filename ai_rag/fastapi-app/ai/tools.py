"""Agent Tool

Which tools an Agent can use is determined by the function_tool table, not by how many functions are written in this file
Tools with enabled set to "No" are not included in the tool list provided to the model during runtime
This switch is real: after an administrator disables it on the page, the model will no longer be able to use it in its next execution

Adding a new tool requires two steps, both are essential

    1. Write an implementation function here and register it in IMPLEMENTATIONS
    2. Insert a record into the function_tool table with tool_code matching the function name

Only doing the first step means the tool will not be enabled; only doing the second step will result in an error when called
"""

import json

from common.exception_handler import CustomException
from common.times import cost_millis, now
from models import FunctionTool, KnowledgeDocument, ToolCallLog


async def search_knowledge(query: str, kb_id: int, top_k: int = 5) -> dict:
    """Search for information in a specified knowledge base

    The main tool for the Agent, internally following the complete retrieval chain from chapters 15 to 19
    """
    # Import within the function to avoid cross-references between the service and the ai layers when loading modules
    from service import retrieval_service

    strategy = await retrieval_service.load_strategy(None)
    outcome = await retrieval_service.retrieve([kb_id], query, strategy)
    return {
        "count": len(outcome["results"]),
        "results": [
            {
                "chunk_id": item["chunk_id"],
                "document_id": item.get("document_id"),
                "score": item.get("score"),
                "content": item["content"],
            }
            for item in outcome["results"][:top_k]
        ],
    }


async def list_documents(kb_id: int) -> dict:
    """Search for documents in this knowledge base

    Used to answer questions like "What documents are in the knowledge base" - these questions cannot be answered by retrieval
    Because the answer is not in any segment, but in the list of documents
    """
    documents = await KnowledgeDocument.filter(kb_id=kb_id).order_by("id").limit(50)
    return {
        "count": len(documents),
        "documents": [
            {"id": doc.id, "name": doc.name, "file_type": doc.file_type, "chunk_count": doc.chunk_count}
            for doc in documents
        ],
    }


async def get_document_detail(document_id: int) -> dict:
    """Search for the details of a document by its document ID"""
    doc = await KnowledgeDocument.get_or_none(id=document_id)
    if doc is None:
        raise CustomException("Document not found")
    return {
        "id": doc.id,
        "name": doc.name,
        "file_type": doc.file_type,
        "char_count": doc.char_count,
        "chunk_count": doc.chunk_count,
        "parse_status": doc.parse_status,
        "vector_status": doc.vector_status,
    }


# tool_code to map the realization function. Tool_code in the table must find the corresponding function here
IMPLEMENTATIONS = {
    "search_knowledge": search_knowledge,
    "list_documents": list_documents,
    "get_document_detail": get_document_detail,
}


async def load_enabled_tools() -> list[dict]:
    """Read out the list of enabled tools that have implementations in the code

    Both conditions are required
    Disabled tools in the table are not provided to the model; enabled tools without code implementations are also not provided
    Otherwise, the model will call a tool that cannot be executed
    """
    tools = await FunctionTool.filter(enabled="Yes").order_by("sort", "id")
    usable = []
    for tool in tools:
        if tool.tool_code not in IMPLEMENTATIONS:
            continue
        usable.append(
            {
                "tool_code": tool.tool_code,
                "tool_name": tool.tool_name,
                "description": tool.description,
                "input_schema": tool.input_schema,
            }
        )
    return usable


def to_openai_tools(tools: list[dict]) -> list[dict]:
    """Convert the tool list into a structure recognizable by the model

    Use the text directly from the table for description; when an administrator changes the description, the model will follow the change in its next judgment
    No need to change code or restart
    """
    definitions = []
    for tool in tools:
        try:
            schema = json.loads(tool["input_schema"]) if tool["input_schema"] else {}
        except json.JSONDecodeError:
            # It's just that, in the form, JSON was wrong to write that it shouldn't be a dead end to the whole operation.
            schema = {}
        definitions.append(
            {
                "type": "function",
                "function": {
                    "name": tool["tool_code"],
                    "description": tool["description"] or tool["tool_name"],
                    "parameters": {
                        "type": "object",
                        "properties": {
                            key: {"type": "string", "description": str(value)}
                            for key, value in schema.items()
                        },
                    },
                },
            }
        )
    return definitions


async def invoke(tool_code: str, params: dict, run_id: int | None = None, step_id: int | None = None) -> dict:
    """Execute a tool and record the log

    Record a log for both success and failure; write the reason into error_message on failure
    The tool call log page in chapter 21 relies on this to statistics the success rate of each tool
    """
    tool = await FunctionTool.get_or_none(tool_code=tool_code)
    if tool is None:
        raise CustomException(f"Tool {tool_code} Not Registered")
    # Check the powering state again on run to block "Model with old list mode deactivated tool"
    if tool.enabled != "Yes":
        raise CustomException(f"Tool {tool.tool_name} Is Disabled")
    implementation = IMPLEMENTATIONS.get(tool_code)
    if implementation is None:
        raise CustomException(f"Tool {tool_code} No Corresponding Implementation")
    started = now()
    try:
        result = await implementation(**params)
        await ToolCallLog.create(
            run_id=run_id,
            step_id=step_id,
            tool_code=tool_code,
            tool_name=tool.tool_name,
            request_params=json.dumps(params, ensure_ascii=False),
            response_result=json.dumps(result, ensure_ascii=False, default=str)[:60000],
            call_status="Succeeded",
            cost_millis=cost_millis(started),
        )
        return result
    except Exception as exc:
        message = exc.message if isinstance(exc, CustomException) else str(exc)
        await ToolCallLog.create(
            run_id=run_id,
            step_id=step_id,
            tool_code=tool_code,
            tool_name=tool.tool_name,
            request_params=json.dumps(params, ensure_ascii=False),
            call_status="Failed",
            # Column Width is varchar (500), pre-store cut
            error_message=message[:500],
            cost_millis=cost_millis(started),
        )
        raise
