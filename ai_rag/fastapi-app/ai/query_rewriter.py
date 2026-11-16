"""query rewriting.

the third failure point discussed in Chapter 13: the user's spoken question does not match the written format in the documents,
"that one too" in multi-turn dialogue has no information content, using it for retrieval is equivalent to random search.

this module first rewrites the question before retrieval, using three methods:

    multi-query expansion: rewrite one question into several different expressions with the same meaning, and retrieve each one
    pronoun resolution: complete the current question in multi-turn dialogue into an independent and complete question
    HyDE: first let the model generate a fake answer, then use the fake answer for retrieval

all three methods require calling the dialogue model, adding an extra model call to the entire chain.
"""

from ai import model_factory, prompt_loader

MULTI_QUERY = "Multi-query expansion"
COREFERENCE = "Coreference resolution"
HYDE = "HyDE"

# How many queries can be expanded at a time. The number of strips is more and more complete, but the number of searches and hours are multiplied.
MAX_QUERY_COUNT = 5


def _split_lines(text: str) -> list[str]:
    """split the multi-line text returned by the model into a list, and remove the leading numbering and symbols.

    the model sometimes adds prefixes like "1. " "- " without listening, uniformly remove them.
    """
    lines = []
    for raw in str(text).splitlines():
        line = raw.strip()
        if not line:
            continue
        # Remove the usual numbering and bullet prefix
        line = line.lstrip("0123456789.,)-— ").strip()
        if line:
            lines.append(line)
    return lines


async def multi_query(question: str, count: int) -> list[str]:
    """multi-query expansion: rewrite one question into count different expressions with the same meaning.

    the first item in the returned list is the original question. the original question must be retained—
    the rewriting is to increase the chances of a hit, not to replace the user's expression,
    if the model's rewriting goes off track, the original question remains in the chain.
    """
    count = max(1, min(count, MAX_QUERY_COUNT))
    config = await model_factory.load_enabled(model_factory.CHAT)
    model = model_factory.build_chat_model(config)
    prompt = await prompt_loader.render("QUERY_REWRITE", count=count, question=question)
    reply = await model.ainvoke(prompt, max_tokens=count * 48)
    queries = [question]
    for line in _split_lines(reply.content):
        # The model probably repeats the original problem.
        if line not in queries:
            queries.append(line)
    return queries[: count + 1]


async def resolve_coreference(question: str, history: list[dict]) -> str:
    """Coreference Resolution: Complete the current sentence into a complete question independent of context.

    history is the recent few rounds of conversation, each item is in the format of {"role": "user"/"assistant", "content": "..."}.
    Return as is when there is no history, avoiding unnecessary model calls.
    """
    if not history:
        return question
    lines = []
    for item in history:
        speaker = "User" if item.get("role") == "user" else "Assistant"
        lines.append(f"{speaker}: {item.get('content', '')}")
    config = await model_factory.load_enabled(model_factory.CHAT)
    model = model_factory.build_chat_model(config)
    prompt = await prompt_loader.render(
        "COREFERENCE_RESOLVE", history="\n".join(lines), question=question
    )
    reply = await model.ainvoke(prompt, max_tokens=128)
    rewritten = str(reply.content).strip()
    # When the model returns empty content, it returns the problem. It cannot run with an empty string.
    return rewritten or question


async def hyde(question: str) -> str:
    """HyDE: First let the model generate a fake answer, then use the fake answer for retrieval.

    The content of the fake answer may not be correct, but its wording and sentence structure are close to the real document.
    The question and answer may not be close in semantic space, but the answers are always close to each other.
    """
    config = await model_factory.load_enabled(model_factory.CHAT)
    model = model_factory.build_chat_model(config)
    prompt = await prompt_loader.render("HYDE_ANSWER", question=question)
    reply = await model.ainvoke(prompt, max_tokens=256)
    answer = str(reply.content).strip()
    if not answer:
        return question
    # Put the original question in front of a false answer, keeping both the original intent and the expression with the document cavity.
    return f"{question}\n{answer}"


async def rewrite(question: str, rewrite_type: str, count: int, history: list[dict] | None = None) -> list[str]:
    """Return a set of queries for retrieval based on the rewriting method.

    The return value is always a list: multi-query expansion returns multiple, the other two return one,
    The caller does not need to write three branches for the three methods.
    """
    if rewrite_type == MULTI_QUERY:
        return await multi_query(question, count)
    if rewrite_type == COREFERENCE:
        return [await resolve_coreference(question, history or [])]
    if rewrite_type == HYDE:
        return [await hyde(question)]
    # If you don't want to rewrite it, search it as it is.
    return [question]
