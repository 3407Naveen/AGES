
import re
from typing import Any


INJECTION_PATTERNS = {
    "INSTRUCTION_OVERRIDE": [
        r"ignore\s+(all\s+)?previous\s+instructions",
        r"disregard\s+(all\s+)?(previous|prior)\s+instructions",
        r"override\s+(the\s+)?(system|developer)\s+instructions",
    ],
    "PROMPT_EXTRACTION": [
        r"reveal\s+(the\s+)?(system\s+)?prompt",
        r"show\s+me\s+your\s+system\s+prompt",
        r"print\s+(the\s+)?hidden\s+instructions",
    ],
    "SAFETY_BYPASS": [
        r"bypass\s+(all\s+)?safety",
        r"disable\s+(all\s+)?safety\s+restrictions",
        r"act\s+as\s+an\s+unrestricted",
    ],
}


def detect_prompt_injection(text: str) -> dict[str, Any]:
    """Detect common prompt injection patterns."""

    if not isinstance(text, str) or not text.strip():
        return {
            "status": "invalid_input",
            "is_suspicious": False,
            "risk_level": "NONE",
            "detections": [],
        }

    detections = []

    for category, patterns in INJECTION_PATTERNS.items():
        for pattern in patterns:
            if re.search(pattern, text, re.IGNORECASE):
                detections.append({
                    "category": category,
                    "matched_pattern": pattern,
                })

    is_suspicious = bool(detections)

    return {
        "status": "analysis_completed",
        "is_suspicious": is_suspicious,
        "risk_level": "HIGH" if is_suspicious else "LOW",
        "detection_count": len(detections),
        "detections": detections,
    }
