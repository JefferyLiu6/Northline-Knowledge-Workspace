"""Agentic RAG State Diagram

The diagram drawn in Chapter 20 is implemented here:

    Query Rewriting ─→ Retrieval ─→ Relevance Scoring ─┬─Relevant──→ Generation ─→ Hallucination Check ─┬─Supported─→ End
                    ↑              ├─Irrelevant─→ Back to Query Rewriting         ├─Not Supported─→ Back to Generation
                    └──────────────┘                          └─Exceeded Limit─→ Fallback
                                   └─Exceeded Limit─→ Fallback

Difference from the straight-line flow in Chapters 15 to 19 is only one: how many rounds to run is decided by the model's judgment, not configuration
The retrieval node still uses the full retrieval chain from retrieval_service, no changes at all

The four hard-coded limits to prevent out-of-control are written in this module, not in configuration, to avoid being changed to a dangerous value
"""

import re

from typing import Annotated, Any, Callable, TypedDict

from langgraph.graph import END, START, StateGraph

from ai import model_factory, prompt_loader, query_rewriter

# The status chart allows as many nodes as possible. LangGraph also has a ceiling on the business side.
MAX_GRAPH_STEPS = 10
# Retrievals were deemed irrelevant, and re-read at most several times
MAX_RETRIEVE_RETRY = 3
# The answer is determined to be several times at most when it is not supported by information.
# The answer is judged to be unsupported, and regenerative at most a few times.
MAX_REGENERATE = 2
# Adds up to a few words to Prompt's information to prevent it from being embroiled in context
MAX_CONTEXT_CHARS = 6000


class AgentState(TypedDict, total=False):
    """The state is passed from start to end, each node only returns the fields it modified, the framework handles merging"""

    # The user's original problem, it's always the same. It's to be used when you go in and out of stock.
    original_query: str
    # The problem with the current round actually being searched will be changed by rewrite nodes.
    query: str
    kb_ids: list[int]
    # The history of multiple rounds of dialogue, which means decomposition.
    history: list[dict]
    # Current recall session
    documents: list[dict]
    # The answer that is generated
    answer: str
    # It's been re-readed several times.
    retry_count: int
    # It's been regenerated several times.
    regenerate_count: int
    # There have been several searches, and we're going to check it out.
    retrieve_count: int
    # Conclusions of the most recent correlation rating and hallucination check
    is_relevant: bool
    is_grounded: bool
    # End cause: normal answer / recall irrelevant / answer is not supported / steps are exceeded
    finish_reason: str
    # Record the echo of each node's performance from the service layer
    on_step: Any


def build_context(documents: list[dict]) -> str:
    """Paste the retrieved fragments into a passage to send to the model

    Truncate if exceeding the length limit, prefer fewer fragments over a failed request due to excessive length
    """
    parts = []
    used = 0
    for index, item in enumerate(documents, start=1):
        content = item.get("content", "")
        if used + len(content) > MAX_CONTEXT_CHARS:
            break
        parts.append(f"[Source {index}] {content}")
        used += len(content)
    return "\n\n".join(parts)


async def _chat(prompt: str, max_tokens: int) -> str:
    """Call a conversation model and extract the text content"""
    config = await model_factory.load_enabled(model_factory.CHAT)
    model = model_factory.build_chat_model(config)
    reply = await model.ainvoke(prompt, max_tokens=max_tokens)
    return str(reply.content).strip()


async def _emit(state: AgentState, node: str, name: str, request: dict, response: dict) -> None:
    """Delegate this step to the service layer for database storage

    The diagram itself does not touch the database, how to record is decided by the external callback injected
    This allows for separate testing from the database.
    """
    callback: Callable | None = state.get("on_step")
    if callback is not None:
        await callback(node, name, request, response)


async def rewrite_node(state: AgentState) -> AgentState:
    """Rewrite queries.

    The first round of direct use of the original problem can be really rewritten only when it is judged irrelevant and returned to this node for re-testing -
    The first round of rewording would be tantamount to abandoning the original expression of the user and could instead lead in a biased direction.
    """
    retry = state.get("retry_count", 0)
    if retry == 0:
        history = state.get("history") or []
        # The first round of the multi-round dialogue will be finger sterilizing, otherwise "it" won't be able to retrieve it.
        query = (
            await query_rewriter.resolve_coreference(state["original_query"], history)
            if history
            else state["original_query"]
        )
        await _emit(state, "rewrite", "Prepare search query", {"retry": retry}, {"query": query})
        return {"query": query}
    queries = await query_rewriter.multi_query(state["original_query"], 2)
    # Try again, take the last one in the rewrite and avoid the last round already used.
    query = queries[-1]
    await _emit(state, "rewrite", f"Rewrite query (attempt {retry})", {"retry": retry}, {"query": query})
    return {"query": query}


async def retrieve_node(state: AgentState) -> AgentState:
    """Retrieves the knowledge base. Inside is a complete link from chapter 15 to chapter 19."""
    from ai import tools

    kb_id = state["kb_ids"][0]
    result = await tools.invoke(
        "search_knowledge",
        {"query": state["query"], "kb_id": kb_id, "top_k": 5},
    )
    documents = result.get("results", [])
    await _emit(
        state,
        "retrieve",
        "Retrieval knowledge base",
        {"query": state["query"], "kb_id": kb_id},
        {"count": len(documents)},
    )
    return {
        "documents": documents,
        "retrieve_count": state.get("retrieve_count", 0) + 1,
    }


async def grade_node(state: AgentState) -> AgentState:
    """Relevance rating: let the model judge whether this information can answer questions."""
    documents = state.get("documents") or []
    if not documents:
        await _emit(state, "grade", "Determining whether recall is relevant or not", {"count": 0}, {"relevant": False})
        return {"is_relevant": False, "retry_count": state.get("retry_count", 0) + 1}
    prompt = await prompt_loader.render(
        "CONTEXT_GRADE",
        context=build_context(documents),
        question=state["original_query"],
    )
    verdict = await _chat(prompt, max_tokens=32)
    # The template requires only "relevant" or "not relevant", and here the tolerance model says two more words.
    relevant = bool(re.search(r"\brelevant\b|\u76f8\u5173", verdict, re.IGNORECASE)) and not bool(
        re.search(r"\b(?:irrelevant|not relevant)\b|\u4e0d\u76f8\u5173", verdict, re.IGNORECASE)
    )
    await _emit(
        state,
        "grade",
        "Determining whether recall is relevant or not",
        {"count": len(documents)},
        {"verdict": verdict, "relevant": relevant},
    )
    if relevant:
        return {"is_relevant": True}
    return {"is_relevant": False, "retry_count": state.get("retry_count", 0) + 1}


async def generate_node(state: AgentState) -> AgentState:
    """Generate answers based on information."""
    prompt = await prompt_loader.render(
        "RAG_ANSWER",
        context=build_context(state.get("documents") or []),
        question=state["original_query"],
    )
    answer = await _chat(prompt, max_tokens=768)
    await _emit(
        state,
        "generate",
        "Generate an answer",
        {"regenerate": state.get("regenerate_count", 0)},
        {"length": len(answer)},
    )
    return {"answer": answer}


async def check_node(state: AgentState) -> AgentState:
    """Illustrative verification: whether or not the answer is entirely supported by information."""
    prompt = await prompt_loader.render(
        "HALLUCINATION_CHECK",
        context=build_context(state.get("documents") or []),
        answer=state.get("answer", ""),
    )
    verdict = await _chat(prompt, max_tokens=32)
    grounded = bool(re.search(r"\bsupported\b|\u6709\u652f\u6491", verdict, re.IGNORECASE)) and not bool(
        re.search(r"\b(?:unsupported|not supported)\b|\u65e0\u652f\u6491", verdict, re.IGNORECASE)
    )
    await _emit(
        state,
        "check",
        "Verify whether the answer is supported by information",
        {"answer_length": len(state.get("answer", ""))},
        {"verdict": verdict, "grounded": grounded},
    )
    if grounded:
        return {"is_grounded": True, "finish_reason": "Answered"}
    return {
        "is_grounded": False,
        "regenerate_count": state.get("regenerate_count", 0) + 1,
    }


async def fallback_node(state: AgentState) -> AgentState:
    """(b) A cover: when information is above the upper limit or is not actually available, the user is explicitly told that it has not been found."""
    reason = state.get("finish_reason") or "Irrelevant retrieval results"
    await _emit(state, "fallback", "I'm going to go for it.", {"reason": reason}, {})
    return {
        "answer": "No relevant content was found in the knowledge base.",
        "finish_reason": reason,
        # Clear quotes when you go around, avoid a bunch of sources on the page that have nothing to do with answers.
        "documents": [],
    }


def route_after_grade(state: AgentState) -> str:
    """Where to after the correlation rating."""
    if state.get("is_relevant"):
        return "generate"
    if state.get("retry_count", 0) >= MAX_RETRIEVE_RETRY:
        # It's not relevant to re-trying the ceiling, which means there's probably no rate in the knowledge base.
        return "fallback"
    return "rewrite"


def route_after_check(state: AgentState) -> str:
    """Where to after the hallucination check."""
    if state.get("is_grounded"):
        return END
    if state.get("regenerate_count", 0) >= MAX_REGENERATE:
        return "fallback"
    return "generate"


def build_graph():
    """Set the nodes and sides together as a status map.

    The process is written on the edge, business in nodes and status in one place.
    Look at this function. It's a flow chart. You don't have to simulate it.
    """
    graph = StateGraph(AgentState)
    graph.add_node("rewrite", rewrite_node)
    graph.add_node("retrieve", retrieve_node)
    graph.add_node("grade", grade_node)
    graph.add_node("generate", generate_node)
    graph.add_node("check", check_node)
    graph.add_node("fallback", fallback_node)

    graph.add_edge(START, "rewrite")
    graph.add_edge("rewrite", "retrieve")
    graph.add_edge("retrieve", "grade")
    # Conditional: Where next is determined by the route_after_grade reading status
    graph.add_conditional_edges(
        "grade",
        route_after_grade,
        {"generate": "generate", "rewrite": "rewrite", "fallback": "fallback"},
    )
    graph.add_edge("generate", "check")
    graph.add_conditional_edges(
        "check",
        route_after_check,
        {END: END, "generate": "generate", "fallback": "fallback"},
    )
    graph.add_edge("fallback", END)
    return graph.compile()
