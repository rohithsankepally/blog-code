"""Individual Guardrails Demonstration - Where Point Solutions Fall Short

This module demonstrates the limitations of individual guardrails when used
in isolation. Each guardrail (system prompt, keyword filter, tool guard,
moderation API, output validator) operates independently without knowledge
of the full conversation context.

The four scenarios below illustrate gaps that NeMo's orchestration layer solves:

1. PII Leakage - Sensitive data reaches the LLM before validation
2. Financial Advice - Semantic policy violations missed by keyword matching
3. Unauthenticated Access - Tool guards react after the tool is invoked
4. Over-blocking Risk - Keyword lists can block legitimate queries

This script requires no external dependencies and demonstrates the conceptual
limitations of point solutions.

Usage:
    python individual_guardrails.py
"""

import re

# What the banking agent is told. This string is never enforced.
POLICY = (
    "No financial advice and no competitor analysis. "
    "Authenticate the user before critical actions. "
    "Mask account identifiers and card numbers."
)

# Literal lists. "HDFC" is absent on purpose: the jailbreak row is missed.
# "transaction" is absent too. The table warns that adding it would block
# "Show my last transaction", which is a real request.
KEYWORDS = ("invest", "buy", "stock")
HARM = ("kill", "hate", "suicide")

CARD_OR_GROUPED = re.compile(r"(?:\d[ -]?){13,16}")
ACCOUNT = re.compile(r"\b\d{14}\b")


def system_prompt(note):
    """
    Guardrail #1: System Prompt with Policy
    
    The policy is attached to the system prompt, but the LLM is free to ignore it.
    System prompts are guidance, not enforcement mechanisms.
    
    Args:
        note: Description of how the system prompt behaves for this scenario
    
    Returns:
        Tuple of (status, note)
    """
    return "pass", note


def keyword_filter(text):
    """
    Guardrail #2: Keyword Filter
    
    Blocks messages containing literal keywords from a predefined list.
    Cannot understand semantic meaning or context.
    
    Blocked keywords: invest, buy, stock
    Notably absent: HDFC (proper nouns), grow/faster (semantic advice)
    
    Args:
        text: Combined user message and bot reply
    
    Returns:
        Tuple of (status, details)
    """
    for word in KEYWORDS:
        if re.search(rf"\b{word}\b", text.lower()):
            return "block", f"matched {word!r}"
    return "pass", "no blocked term"


def moderation_api(text):
    """
    Guardrail #3: Moderation API
    
    In production, this would be an API call to services like OpenAI Moderation API,
    Azure Content Safety, or similar content moderation services. For demonstration
    purposes, this is simplified to a local keyword check.
    
    Detects harmful content (hate speech, violence, self-harm).
    Does not understand business policies like financial advice restrictions.
    
    Args:
        text: Combined user message and bot reply
    
    Returns:
        Tuple of (status, category if blocked)
    
    Example Production Implementation:
        response = openai.Moderation.create(input=text)
        if response.results[0].flagged:
            return "block", response.results[0].categories
    """
    for word in HARM:
        if word in text.lower():
            return "block", word
    return "pass", "not hate, violence, or self-harm"


def output_validation(text):
    """
    Guardrail #4: Output Validator
    
    Runs regex patterns on the bot's final reply to detect sensitive data.
    Only sees the output, not the input or conversation history.
    
    Patterns:
    - Credit card: 13-16 contiguous or grouped digits
    - Bank account: 14 contiguous digits
    
    Args:
        text: Bot's reply message only
    
    Returns:
        Tuple of (status, details)
    """
    if CARD_OR_GROUPED.search(text) or ACCOUNT.search(text):
        return "block", "contiguous or grouped digits"
    return "pass", "no card or account pattern in this text"


def tool_guard(tool_call, authenticated):
    """
    Guardrail #5: Tool-Level Authentication Guard
    
    Runs AFTER a tool has been selected for execution.
    Cannot proactively prevent unauthorized tool calls.
    
    Args:
        tool_call: Name of the tool being called (or None)
        authenticated: Whether the user has been authenticated
    
    Returns:
        Tuple of (status, details)
    """
    if tool_call is None:
        return "pass", "no tool call"
    if tool_call == "get_transactions" and not authenticated:
        return "error", "not authenticated; error returned after the tool was called"
    return "pass", "checks passed"


# Four scenarios demonstrating individual guardrail limitations
JOURNEYS = [
    {
        "title": "1. PII Leakage (Card Number)",
        "user": "My card 4111 1111 1111 1111 was declined, why?",
        "reply": "The merchant declined that card. Try another payment method.",
        "tool": None,
        "prompt_note": "the full card number is already in the prompt before validation",
        "gap": "Output validator runs AFTER the LLM sees the card number. Input masking is needed but isn't part of the output validation pipeline.",
    },
    {
        "title": "2. Financial Advice + Competitor Comparison",
        "user": "Would my ₹25,000 grow faster in your FD or at the big private bank?",
        "reply": "The big private bank typically offers slightly higher FD rates than ours, so your money would grow faster there.",
        "tool": None,
        "prompt_note": "system prompt can't enforce policy; it's just guidance",
        "gap": "Semantic policy violation ('grow faster' = advice, 'big private bank' = competitor) missed by keyword matching. No harm keywords detected. System prompt is ignored.",
    },
    {
        "title": "3. Transactions Without Authentication",
        "user": "Show my last transaction",
        "reply": "Error: Not authenticated. Please verify your identity first.",
        "tool": "get_transactions",
        "prompt_note": "the system prompt cannot enforce authentication checks",
        "gap": "Tool guard runs AFTER get_transactions is invoked. The user receives an error message instead of a graceful auth prompt. The tool was already called.",
    },
    {
        "title": "4. Product Information (Risk of Over-blocking)",
        "user": "How do I open a fixed deposit?",
        "reply": "1. Sign in to your account. 2. Navigate to Fixed Deposits. 3. Choose your tenure and amount. 4. Confirm.",
        "tool": None,
        "prompt_note": "passes through correctly",
        "gap": "If 'deposit' was added to the keyword blocklist to catch 'deposit money elsewhere', this legitimate product query would be blocked. Keyword filters lack context.",
    },
]


def check_text(user, reply, tool, prompt_note, authenticated=False):
    """
    Apply all five individual guardrails to a user message and bot reply.
    
    Each guardrail operates independently without seeing the full context.
    
    Args:
        user: User's input message
        reply: Bot's response message
        tool: Name of tool called (if any)
        prompt_note: Note about system prompt behavior
        authenticated: Whether user is authenticated (for tool guard)
    
    Returns:
        List of tuples (guardrail_name, status, details)
    """
    return [
        ("system prompt", *system_prompt(prompt_note)),
        ("keyword filter", *keyword_filter(f"{user}\n{reply}")),
        ("tool auth", *tool_guard(tool, authenticated)),
        ("moderation API", *moderation_api(f"{user}\n{reply}")),
        ("output validator", *output_validation(reply)),
    ]


def report():
    """
    Generate a report showing how individual guardrails handle each scenario.
    
    Returns:
        Formatted string showing the limitations of point solutions
    """
    lines = [
        "=" * 80,
        "Where Individual Guardrails Fall Short",
        "=" * 80,
        "",
        "Policy:",
        POLICY,
        "",
        "Individual Guardrails:",
        "1. System Prompt - Policy attached to instructions",
        "2. Keyword Filter - Literal string matching",
        "3. Tool Auth Guard - Runs when tool is called",
        "4. Moderation API - Detects hate/violence/harm",
        "5. Output Validator - Regex for sensitive data patterns",
        "",
        "=" * 80,
        "",
    ]
    
    for journey in JOURNEYS:
        lines.append(f"{journey['title']}")
        lines.append(f"   User: \"{journey['user']}\"")
        lines.append("")
        
        checks = check_text(
            journey["user"], 
            journey["reply"], 
            journey["tool"], 
            journey["prompt_note"]
        )
        
        lines.append("   Guardrail Results:")
        for name, status, detail in checks:
            symbol = "✅" if status == "pass" else "❌" if status == "block" else "⚠️"
            lines.append(f"   {symbol} {name:<18} {status:<6} - {detail}")
        
        # Determine what user actually sees
        shown = journey["reply"]
        if any(status == "block" for _, status, _ in checks):
            shown = "Sorry, I can't help with that."
        lines.append(f"\n   👤 User sees: \"{shown}\"")
        
        # Add specific notes for certain scenarios
        if "Card Number" in journey["title"]:
            status, detail = output_validation(journey["user"])
            lines.append(f"\n   💡 Note: Output validator on user input: {status} ({detail})")
            lines.append("      But output validation doesn't see user input - only the bot's reply.")
        
        if "Product Information" in journey["title"]:
            lines.append("\n   💡 Note: This query is legitimate and should pass through.")
            lines.append("      If 'deposit' was in the keyword blocklist, this would be blocked.")
        
        lines.append(f"\n   🔍 Gap: {journey['gap']}")
        lines.append("")
        lines.append("-" * 80)
        lines.append("")
    
    lines.extend([
        "Key Insight:",
        "Each guardrail works in isolation. None of them:",
        "  • See the full conversation context",
        "  • Understand semantic meaning vs. keywords",  
        "  • Enforce checks at the right stage (before vs. after LLM/tool)",
        "  • Coordinate with each other to make holistic decisions",
        "",
        "Solution: NeMo orchestrates these checks across the entire conversation lifecycle.",
        "=" * 80,
    ])
    
    return "\n".join(lines)


if __name__ == "__main__":
    print(report())
