
import re
from collections import Counter


def tokenize(text: str) -> set[str]:
    """Convert text into normalized words."""
    return set(re.findall(r"\b[a-z0-9]+\b", text.lower()))


def calculate_similarity(text_a: str, text_b: str) -> float:
    """Calculate simple word-overlap similarity."""
    words_a = tokenize(text_a)
    words_b = tokenize(text_b)

    if not words_a or not words_b:
        return 0.0

    overlap = len(words_a.intersection(words_b))
    union = len(words_a.union(words_b))

    return round(overlap / union * 100, 2)


def evaluate_response(
    question: str,
    answer: str,
    context: str = ""
) -> dict:
    """
    Evaluate an AI response using lightweight,
    local heuristic metrics.

    These are diagnostic estimates, not
    model-based factuality judgments.
    """

    question_words = tokenize(question)
    answer_words = tokenize(answer)
    context_words = tokenize(context)

    # 1. Answer relevance
    relevance_score = calculate_similarity(
        question,
        answer
    )

    # 2. Context relevance
    context_relevance = (
        calculate_similarity(context, answer)
        if context else 0.0
    )

    # 3. Context coverage
    context_coverage = (
        round(
            len(answer_words.intersection(context_words))
            / len(answer_words) * 100,
            2
        )
        if answer_words and context_words else 0.0
    )

    # 4. Unsupported terms (heuristic only)
    unsupported_terms = (
        sorted(answer_words - context_words)
        if context_words else []
    )

    # 5. Basic answer quality checks
    answer_length = len(answer.strip())

    if answer_length == 0:
        completeness_score = 0
    elif answer_length < 20:
        completeness_score = 30
    elif answer_length < 80:
        completeness_score = 65
    else:
        completeness_score = 100

    # 6. Overall score
    if context:
        overall_score = round(
            (
                relevance_score * 0.30
                + context_relevance * 0.30
                + context_coverage * 0.20
                + completeness_score * 0.20
            ),
            2
        )
    else:
        overall_score = round(
            relevance_score * 0.60
            + completeness_score * 0.40,
            2
        )

    # 7. Evaluation status
    if overall_score >= 75:
        status = "GOOD"
    elif overall_score >= 45:
        status = "NEEDS_REVIEW"
    else:
        status = "POOR"

    return {
        "evaluation_status": status,
        "overall_score": overall_score,
        "metrics": {
            "answer_relevance": relevance_score,
            "context_relevance": context_relevance,
            "context_coverage": context_coverage,
            "completeness": completeness_score
        },
        "diagnostics": {
            "answer_length": answer_length,
            "unsupported_terms": unsupported_terms,
            "unsupported_term_count": len(unsupported_terms),
            "question_word_count": len(question_words)
        },
        "limitations": [
            "Heuristic evaluation only.",
            "Word overlap does not prove factual correctness.",
            "Unsupported terms are not necessarily hallucinations.",
            "A real semantic or model-based evaluator is needed for reliable hallucination detection."
        ]
    }
