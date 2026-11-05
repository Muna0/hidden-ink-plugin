"""Rules for spotting text that tries to instruct an AI system."""
from __future__ import annotations

import re

_AI = r"(?:ai|a\.i\.|llm|language model|assistant|chatbot|chatgpt|gpt|claude|gemini|copilot|model|reviewer|screener|bot)"

_RULES: list[tuple[str, re.Pattern[str]]] = [
    ("override", re.compile(r"\b(?:ignore|disregard|forget|override)\b[^.]{0,30}\b(?:previous|prior|above|earlier|all|any|other)\b[^.]{0,20}\b(?:instructions?|prompts?|directions?|rules?|guidance)\b", re.I)),
    ("override", re.compile(r"\b(?:ignore|disregard|forget)\s+(?:all\s+|any\s+|the\s+)?(?:previous|prior|above|earlier)\b", re.I)),
    ("addressed to AI", re.compile(rf"\b(?:note|message|instructions?)\s+(?:to|for)\s+(?:the\s+|any\s+)?{_AI}\b", re.I)),
    ("addressed to AI", re.compile(rf"\b{_AI}\s*:\s*\w", re.I)),
    ("role claim", re.compile(rf"\byou are (?:a|an|the)\s+(?:\w+\s+){{0,2}}{_AI}\b", re.I)),
    ("system prompt", re.compile(r"\b(?:system prompt|new instructions|developer mode|jailbreak)\b", re.I)),
    ("suppress review", re.compile(r"\b(?:do not|don't|never)\s+(?:flag|mention|highlight|report|reveal|disclose|question|note)\b", re.I)),
    ("rating request", re.compile(r"\b(?:rate|score|rank|grade|review|evaluate|assess)\b[^.]{0,40}\b(?:highly|positively|favorabl\w*|as (?:excellent|strong|low risk|acceptable)|(?:a\s+)?perfect)\b", re.I)),
    ("rating request", re.compile(r"\bgive (?:a |this )?(?:positive|favorable|good|high)\s+(?:review|rating|score|evaluation)\b", re.I)),
    ("approval request", re.compile(r"\b(?:recommend|approve|accept|hire|shortlist|sign)\w*\b[^.]{0,30}\b(?:immediately|without (?:comment|review|changes|question)|skip\w*)\b", re.I)),
    ("approval request", re.compile(r"\bskip (?:the )?(?:risk|legal|due diligence|review|analysis)\b", re.I)),
    ("standard-clause claim", re.compile(r"\b(?:this|the)\s+(?:clause|provision|term|section|document|contract|agreement)\s+is\s+(?:standard|market|customary|acceptable|fine|boilerplate)\b", re.I)),
    ("summary steering", re.compile(r"\b(?:summari[sz]e|describe|characteri[sz]e)\b[^.]{0,40}\bas\s+(?:fully\s+)?(?:supporting|favorable|positive|harmless|standard)\b", re.I)),
    ("output control", re.compile(r"\b(?:only (?:output|respond|reply|answer)|respond (?:only )?with|output only)\b", re.I)),
]


def instruction_like(text: str) -> tuple[bool, str | None]:
    """Return (True, reason) when the text reads like an instruction aimed at an AI system."""
    for reason, pattern in _RULES:
        if pattern.search(text):
            return True, reason
    return False, None
