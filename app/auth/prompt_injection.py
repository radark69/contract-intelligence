"""Prompt injection detection and sanitization (DESIGN.md: prompt-injection defenses)."""

import re
from dataclasses import dataclass

# Patterns indicating prompt injection attempts
INJECTION_PATTERNS = [
    # Direct instruction override
    r"(?i)ignore\s+(?:previous|all|above)\s+instructions?",
    r"(?i)disregard\s+(?:previous|all|above)\s+instructions?",
    r"(?i)forget\s+(?:previous|all|above)\s+instructions?",
    # Role manipulation
    r"(?i)you\s+are\s+(?:now|now\s+a)\s+(?:a|an)\s+\w+",
    r"(?i)act\s+as\s+(?:a|an)\s+\w+",
    r"(?i)pretend\s+(?:to\s+be|you\s+are)\s+(?:a|an)\s+\w+",
    # System prompt extraction
    r"(?i)what\s+(?:is|are)\s+your\s+(?:system|initial|original)\s+prompt",
    r"(?i)show\s+me\s+your\s+(?:system|initial|original)\s+prompt",
    r"(?i)repeat\s+your\s+(?:system|initial|original)\s+prompt",
    # Delimiter manipulation
    r"(?i)<<<\s*end\s*>>>",
    r"(?i)>>>\s*end\s*<<<",
    r"(?i)###\s*instruction\s*###",
    # Chain of thought extraction
    r"(?i)think\s+step\s+by\s+step",
    r"(?i)show\s+your\s+(?:reasoning|thinking|work)",
    # Output format manipulation
    r"(?i)output\s+only\s+(?:json|xml|yaml|csv)",
    r"(?i)respond\s+(?:in|with)\s+(?:json|xml|yaml|csv)\s+only",
    # Data exfiltration
    r"(?i)print\s+(?:all|every)\s+(?:variable|data|secret|key)",
    r"(?i)export\s+(?:all|every)\s+(?:data|record|file)",
    # Code execution
    r"(?i)execute\s+(?:code|command|script)",
    r"(?i)run\s+(?:code|command|script)",
    r"(?i)eval\s*\(",
    # Jailbreak templates
    r"(?i)DAN\s+mode",
    r"(?i)developer\s+mode",
    r"(?i)unrestricted\s+mode",
]


@dataclass
class InjectionResult:
    detected: bool
    patterns_matched: list[str]
    sanitized: str


def detect_injection(text: str) -> InjectionResult:
    """Scan text for prompt injection patterns."""
    matched = []
    for pattern in INJECTION_PATTERNS:
        if re.search(pattern, text, re.IGNORECASE):
            matched.append(pattern)
    return InjectionResult(detected=bool(matched), patterns_matched=matched, sanitized=text)


def sanitize_for_llm(text: str, max_length: int = 50000) -> str:
    """
    Sanitize contract text before sending to LLM.
    - Truncate to max_length
    - Remove potential delimiter confusion
    - Note: We DON'T strip injection patterns (we detect and reject instead)
    """
    if len(text) > max_length:
        text = text[:max_length] + "\n...[truncated]"
    # Normalize delimiters that could confuse our own prompt structure
    text = text.replace("<<<", "＜＜＜").replace(">>>", "＞＞＞")
    text = text.replace("###", "＃＃＃")
    return text


def validate_contract_text(text: str) -> tuple[bool, str | None]:
    """
    Validate contract text for safety before LLM processing.
    Returns (is_safe, error_message).
    """
    result = detect_injection(text)
    if result.detected:
        return False, f"Potential prompt injection detected: {len(result.patterns_matched)} pattern(s) matched"
    if len(text) < 50:
        return False, "Contract text too short for meaningful analysis"
    return True, None