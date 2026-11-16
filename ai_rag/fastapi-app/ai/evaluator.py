"""Implementation of the four metrics in Chapter 26. All four metrics are semantic judgments, rules cannot be written,

So use large models as judges - this method is called LLM-as-judge.
Context Recall     Can each sentence of the standard answer find support in the retrieved materials

    Context Precision  Are the useful materials in the retrieved materials ranked first
    Faithfulness       Can each sentence of the answer find support in the materials
    Is there any way you can find support in every word of Faithful's answer?
    Answer Relevancy   How close the inferred question from the answer is to the original question

The temperature of the judge model must be 0, otherwise the same passage may be judged as "relevant" one time and "not relevant" another time
The difference between two evaluations cannot distinguish whether the change is due to a strategy shift or judge inconsistency. The model factory in Chapter 11 has been fixed to 0

Two approaches to reduce calls:
    The prompt for judgment classes lets the model judge multiple items at once, not one by one
    When the test case includes reference_chunk_ids, Context Recall directly compares fragment IDs without calling the model
"""

import math
import re

from ai import model_factory, prompt_loader

# How many statements can be judged at a time, and too many models are liable to slip out of order.
MAX_STATEMENTS = 12
# How many words do you want to spell out for the decision?
MAX_JUDGE_CHARS = 5000


async def _chat(prompt: str, max_tokens: int) -> str:
    config = await model_factory.load_enabled(model_factory.CHAT)
    model = model_factory.build_chat_model(config)
    reply = await model.ainvoke(prompt, max_tokens=max_tokens)
    return str(reply.content).strip()


def _clean_lines(text: str) -> list[str]:
    """Clean the model's multi-line output into a list, removing numbering and bullet points"""
    lines = []
    for raw in str(text).splitlines():
        line = raw.strip().lstrip("0123456789.,)-— ").strip()
        if line:
            lines.append(line)
    return lines


def parse_verdicts(text: str, expected: int) -> list[bool]:
    """Parse the model's line-by-line output into a boolean list

    The model occasionally outputs one line more or less, here align with the expected number of items:
    Truncate if more, fill with "No" if less - when unsure, treat as not passed, keeping the score conservative rather than optimistic
    """
    verdicts = []
    for line in _clean_lines(text):
        # Accept English verdicts and the affirmative marker used by older templates.
        verdicts.append(bool(re.match(r"^(?:yes\b|\u662f)", line, re.IGNORECASE)))
    if len(verdicts) > expected:
        return verdicts[:expected]
    return verdicts + [False] * (expected - len(verdicts))


def build_context(contents: list[str]) -> str:
    """Paste the fragments into a passage the judge can read, truncate if too long"""
    parts = []
    used = 0
    for index, content in enumerate(contents, start=1):
        if used + len(content) > MAX_JUDGE_CHARS:
            break
        parts.append(f"[Source {index}] {content}")
        used += len(content)
    return "\n\n".join(parts)


async def split_statements(text: str) -> list[str]:
    """Split a paragraph into several independent statements

    Only after splitting can each statement be judged individually, which is the common premise for Context Recall and Faithfulness
    """
    if not text or not text.strip():
        return []
    prompt = await prompt_loader.render("EVAL_SPLIT_STATEMENTS", text=text.strip())
    statements = _clean_lines(await _chat(prompt, max_tokens=384))
    return statements[:MAX_STATEMENTS]


async def judge_support(context: str, statements: list[str]) -> list[bool]:
    """Judge whether each statement can be inferred from the passage. Judge all items at once with one call, not one by one"""
    if not statements:
        return []
    numbered = "\n".join(f"{index}. {item}" for index, item in enumerate(statements, start=1))
    prompt = await prompt_loader.render(
        "EVAL_JUDGE_SUPPORT", context=context, statements=numbered
    )
    return parse_verdicts(await _chat(prompt, max_tokens=len(statements) * 4 + 12), len(statements))


async def judge_relevance(question: str, contents: list[str]) -> list[bool]:
    """Judge whether each passage is useful for answering the question"""
    if not contents:
        return []
    numbered = "\n\n".join(
        f"[Source {index}] {content[:800]}" for index, content in enumerate(contents, start=1)
    )
    prompt = await prompt_loader.render(
        "EVAL_JUDGE_RELEVANCE", question=question, contexts=numbered
    )
    return parse_verdicts(await _chat(prompt, max_tokens=len(contents) * 4 + 12), len(contents))


async def reverse_question(answer: str) -> str:
    """Infer the question from the answer"""
    if not answer or not answer.strip():
        return ""
    prompt = await prompt_loader.render("EVAL_REVERSE_QUESTION", answer=answer.strip())
    return await _chat(prompt, max_tokens=96)


def cosine(left: list[float], right: list[float]) -> float:
    """Cosine similarity between two vectors"""
    if not left or not right or len(left) != len(right):
        return 0.0
    dot = sum(a * b for a, b in zip(left, right))
    norm_left = math.sqrt(sum(a * a for a in left))
    norm_right = math.sqrt(sum(b * b for b in right))
    if norm_left == 0 or norm_right == 0:
        return 0.0
    return dot / (norm_left * norm_right)


def precision_at_k(relevances: list[bool]) -> float:
    """Calculate context precision with positional weighting

    As mentioned in Chapter 26: the same recall content, the relevant one ranked first and fourth, the precision should be very different
    Here, calculate "precision up to this position" for each relevant position, then take the average:

        Recall [relevant, irrelevant, irrelevant, irrelevant]
            Position 1 is relevant, precision up to here is 1/1 = 1.0
            Precision = 1.0 / 1 = 1.0

        Recall [irrelevant, irrelevant, irrelevant, relevant]
            Position 4 is relevant, precision up to here is 1/4 = 0.25
            Precision = 0.25 / 1 = 0.25
    """
    if not relevances:
        return 0.0
    hit = 0
    total = 0.0
    for index, relevant in enumerate(relevances, start=1):
        if relevant:
            hit += 1
            total += hit / index
    if hit == 0:
        return 0.0
    return total / hit


async def context_recall(ground_truth: str, contents: list[str], reference_chunk_ids: list[int] | None,
                         retrieved_chunk_ids: list[int]) -> float:
    """Context Recall: whether the information in the standard answer is retrieved

    When the test case includes reference_chunk_ids, directly compare fragment IDs without calling the model -
    More accurate and cost-effective, test cases generated in Chapter 27 all include this field
    """
    if reference_chunk_ids:
        expected = set(reference_chunk_ids)
        hit = expected & set(retrieved_chunk_ids)
        return len(hit) / len(expected)
    statements = await split_statements(ground_truth)
    if not statements:
        return 0.0
    verdicts = await judge_support(build_context(contents), statements)
    return sum(1 for item in verdicts if item) / len(verdicts)


async def faithfulness(answer: str, contents: list[str]) -> float:
    """Faithfulness: whether each sentence in the answer is supported by the passage"""
    statements = await split_statements(answer)
    if not statements:
        return 0.0
    verdicts = await judge_support(build_context(contents), statements)
    return sum(1 for item in verdicts if item) / len(verdicts)


async def context_precision(question: str, contents: list[str]) -> float:
    """Context Precision: whether useful passages are ranked higher"""
    relevances = await judge_relevance(question, contents)
    return precision_at_k(relevances)


async def answer_relevancy(question: str, answer: str) -> float:
    """Answer Relevance: how close the inferred question from the answer is to the original question

    Compare using vector similarity, which is much more stable than letting the model score -
    The model gives numbers like "similarity 0.8" casually, while vector calculation is deterministic
    """
    reversed_question = await reverse_question(answer)
    if not reversed_question:
        return 0.0
    config = await model_factory.load_enabled(model_factory.EMBEDDING)
    embeddings = model_factory.build_embeddings(config)
    vectors = await embeddings.aembed_documents([question, reversed_question])
    score = cosine(vectors[0], vectors[1])
    # The cosine is likely to be negative. Negative correlation equals total incoherence, cut to zero.
    return max(0.0, score)


async def evaluate_case(
    question: str,
    ground_truth: str,
    answer: str,
    contents: list[str],
    retrieved_chunk_ids: list[int],
    reference_chunk_ids: list[int] | None = None,
) -> dict:
    """Calculate four metrics for one test case"""
    recall = await context_recall(ground_truth, contents, reference_chunk_ids, retrieved_chunk_ids)
    precision = await context_precision(question, contents)
    faithful = await faithfulness(answer, contents)
    relevancy = await answer_relevancy(question, answer)
    scores = [recall, precision, faithful, relevancy]
    return {
        "context_recall": round(recall, 4),
        "context_precision": round(precision, 4),
        "faithfulness": round(faithful, 4),
        "answer_relevancy": round(relevancy, 4),
        "avg_score": round(sum(scores) / len(scores), 4),
    }
