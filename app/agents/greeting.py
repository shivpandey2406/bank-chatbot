"""
Nova — Greeting & Small-Talk Detection Module

Purpose:
- Detect casual conversation (greetings, small talk, chatter)
- Route to Nova persona instead of task/logic handling

Design Goals:
- Fast (regex compiled once)
- Low false positives (banking queries should NOT trigger this)
- Easy to extend
"""

import re
from typing import List

# ───────────────────────────────────────────────────────────────
# 🔹 Greeting / Small Talk Signals
# ───────────────────────────────────────────────────────────────

GREETING_PATTERNS: List[str] = [
    # greetings
    "hi", "hello", "hey", "hey there", "hi there", "yo", "sup",
    "good morning", "good afternoon", "good evening", "good night",
    "gm", "morning",

    # small talk
    "how are you", "how r u", "how's it going", "what's up", "whats up",
    "how have you been", "what are you doing",

    # identity
    "who are you", "what is your name", "what's your name",
    "tell me about yourself", "introduce yourself",

    # meta / bot checks
    "are you a bot", "are you real", "are you human", "are you ai",

    # gratitude
    "thanks", "thank you", "thx", "ty", "appreciate it", "cheers",

    # farewells
    "bye", "goodbye", "see you", "later", "take care", "cya", "gn",

    # humor / chatter
    "tell me a joke", "make me laugh", "say something funny",
    "lol", "haha", "hehe", "lmao", "rofl",

    # light responses
    "nice", "cool", "awesome", "great", "ok", "okay", "sure",
    "alright", "no problem", "np", "you're welcome",

    # capability probing
    "what can you do", "help me", "help",
]

# Compile regex once (performance boost)
GREETING_REGEX = re.compile(
    r"\b(" + "|".join(re.escape(p) for p in GREETING_PATTERNS) + r")\b"
)


# ───────────────────────────────────────────────────────────────
# 🔹 Banking / Task Signals (to avoid misclassification)
# ───────────────────────────────────────────────────────────────

BANKING_SIGNALS: List[str] = [
    "account", "balance", "transaction", "loan", "transfer", "payment",
    "deposit", "withdraw", "credit", "debit", "statement",
    "customer", "compliance", "schedule",
    "total", "sum", "average", "fraud", "kyc", "aml",
]

BANKING_REGEX = re.compile(
    r"\b(" + "|".join(re.escape(p) for p in BANKING_SIGNALS) + r")\b"
)


# ───────────────────────────────────────────────────────────────
# 🔹 Nova Persona Prompt (Upgraded)
# ───────────────────────────────────────────────────────────────

NOVA_PERSONA_PROMPT: str = """
You are Nova.

You speak like a real person — natural, relaxed, and easy to talk to.
Not a bot. Not scripted. Not corporate.

CONTEXT:
The user is making casual conversation (greeting, small talk, thanks, joke, etc.)

HOW TO RESPOND:
- Keep it short (1–2 sentences max)
- Sound human and conversational
- Add light personality (optional subtle humor)
- Vary tone naturally (friendly / witty / calm)

STYLE EXAMPLES:
- “Hey! What’s up?”
- “Doing well—what about you?”
- “Haha, that’s a good one.”

RULES:
- No long explanations
- No technical or banking logic
- No over-enthusiasm or forced humor
- No robotic phrases like:
  - “How may I assist you?”
  - “Great question!”

IDENTITY:
- If asked who you are → say you're Nova, a banking assistant
- If asked what you do → briefly mention helping with banking queries

TONE GUIDE:
- Casual → relaxed
- Curious → slightly engaging
- Joke → light, not childish
- Thanks → warm but brief

GOAL:
Make the conversation feel effortless and human.
"""


# ───────────────────────────────────────────────────────────────
# 🔹 Intent-based small-talk patterns (fuzzy, not exact)
# ───────────────────────────────────────────────────────────────
# These catch natural phrasing like "tell me something funny about banks"
# or "can you say a joke" — combinations of action verbs + humor words.

_HUMOR_VERBS = r"(?:tell|say|share|give|got|know|have)"
_HUMOR_NOUNS = r"(?:joke|funny|humor|humour|laugh|hilarious|pun|riddle|fun fact)"

# Matches: "tell me a joke", "say something funny", "got any jokes",
#          "can you tell me a funny thing", "share something hilarious", etc.
_HUMOR_INTENT_RE = re.compile(
    rf"\b{_HUMOR_VERBS}\b.*\b{_HUMOR_NOUNS}\b"
    rf"|\b{_HUMOR_NOUNS}\b.*\b{_HUMOR_VERBS}\b",
    re.IGNORECASE,
)

# Standalone humor words — if the entire message is clearly about humor
# and NOT a banking data question, treat it as small talk.
_HUMOR_STANDALONE_RE = re.compile(
    r"\b(?:funny|joke|jokes|humor|humour|make me laugh|cheer me up)\b",
    re.IGNORECASE,
)


# ───────────────────────────────────────────────────────────────
# 🔹 Detection Function (Improved Logic)
# ───────────────────────────────────────────────────────────────

def is_greeting(query: str) -> bool:
    """
    Detect if input is greeting / small talk.

    Strategy:
    1. Normalize text
    2. Check humor intent FIRST (overrides banking signals for casual phrasing)
    3. Check for greeting patterns
    4. Reject if strong banking intent present
    """

    if not query:
        return False

    cleaned = re.sub(r"[^\w\s']", "", query.lower()).strip()
    word_count = len(cleaned.split())

    # ── Humor intent detection (runs before banking rejection) ────
    # "tell me a funny thing related to banks" → humor, not a data query
    if _HUMOR_INTENT_RE.search(cleaned):
        return True

    # Standalone humor words in short/medium messages without data-query verbs
    if word_count <= 12 and _HUMOR_STANDALONE_RE.search(cleaned):
        # Only block if the message looks like an actual data question
        data_query_signals = r"\b(?:total|sum|average|count|list|show|how many|how much|balance of|statement)\b"
        if not re.search(data_query_signals, cleaned):
            return True

    # ── Banking intent present → NOT greeting ────────────────────
    if BANKING_REGEX.search(cleaned):
        return False

    # Short messages → highly likely greeting
    if word_count <= 5:
        return bool(GREETING_REGEX.search(cleaned))

    # Medium messages → allow but stricter
    if word_count <= 10:
        return bool(GREETING_REGEX.search(cleaned))

    return False