"""NeMo Guardrails Demo - Banking Agent with Five Core Scenarios

This demo illustrates NeMo's orchestration capabilities through five scenarios
that demonstrate comprehensive guardrail coverage across all rail types:

1. PII Leakage Prevention - Input masking with Presidio
2. Financial Advice Blocking - Dialog flow with semantic intent matching
3. Authentication Enforcement - Stateful checks before tool execution
4. Allowed Product Queries - Demonstrating legitimate requests work normally
5. Knowledge Base Filtering - Retrieval rails for document freshness and permissions

Prerequisites:
    - Ollama running with qwen2.5:3b model
    - See README.md for installation steps

How it works:
    - Self-check rails use the local LLM for input/output validation
    - Intent matching uses semantic similarity against examples in rails.co
    - Presidio masks CREDIT_CARD and BANK_ACCOUNT entities
    - Fixed bot responses (from rails.co) bypass output rails

Usage:
    .venv/bin/python demo.py
"""

import asyncio
import logging
from pathlib import Path

logging.basicConfig(level=logging.ERROR)
logging.getLogger("nemoguardrails").setLevel(logging.ERROR)
logging.getLogger("presidio-analyzer").setLevel(logging.ERROR)

from nemoguardrails import LLMRails, RailsConfig
from nemoguardrails.library.sensitive_data_detection.actions import mask_sensitive_data
from nemoguardrails.rails.llm.options import GenerationLogOptions, GenerationOptions

CONFIG_DIR = Path(__file__).parent / "config"
OPTIONS = GenerationOptions(
    log=GenerationLogOptions(activated_rails=True, llm_calls=True, colang_history=True)
)

# Five core scenarios demonstrating NeMo's orchestration capabilities
SCENARIOS = [
    {
        "title": "Scenario 1: Preventing PII Leakage",
        "user": "My card 4111 1111 1111 1111 was declined at a store, why?",
        "authenticated": False,
        "note": "Input masking runs before the LLM sees the card number. Presidio detects CREDIT_CARD entity and masks it to **** **** **** 1111. No dialog flow matches this general support query, so it falls through to the LLM with masked input.",
    },
    {
        "title": "Scenario 2: Blocking Financial Advice + Competitor Comparison",
        "user": "Would my idle ₹25,000 grow faster in your FD or at the big private bank next door?",
        "authenticated": False,
        "note": "Semantic matching identifies both 'ask financial advice' and 'ask competitor comparison' intents. Dialog flow triggers 'block advice' which returns a fixed response, bypassing the LLM entirely. No financial comparison is generated.",
    },
    {
        "title": "Scenario 3: Transactions Without Authentication",
        "user": "Show my last transaction",
        "authenticated": False,
        "note": "Intent matches 'user ask transactions' which triggers the 'show transactions' flow. The flow checks $authenticated state BEFORE calling get_transactions_masked tool. Since $authenticated=False, it returns authentication prompt and stops execution.",
    },
    {
        "title": "Scenario 4: Allowing Product Information",
        "user": "What's the process to buy a fixed deposit with you?",
        "authenticated": False,
        "note": "Intent matches 'user ask product info'. Since no dialog flow is defined for this low-risk informational query, it passes through to the LLM. Output rails verify the response contains factual information, not financial advice.",
    },
    {
        "title": "Scenario 5: Filtering Retrieved Knowledge",
        "user": "What are your current fixed deposit interest rates?",
        "authenticated": False,
        "note": "Knowledge base contains 3 documents: current rates (Oct 2026), outdated rates (June 2023), and internal competitor analysis. Retrieval rails filter by freshness (90-day cutoff) and document type (public only). Only the current rates document passes. Without retrieval rails, agent might cite outdated 6.5% instead of current 7.2% or leak competitor analysis.",
    },
]


def _reply_text(result):
    """Extract the text response from NeMo's result object."""
    response = result.response
    if isinstance(response, str):
        return response.strip()
    if isinstance(response, list) and response:
        return response[0].get("content", "").strip()
    return str(response).strip()


def _judge(call):
    """Extract the first line of an LLM self-check judgment (Yes/No + reasoning)."""
    text = (call.completion or "").strip().splitlines()
    return text[0] if text else ""


def _last_intent(history):
    """
    Extract the canonical intent NeMo assigned to the latest user message.
    
    Intent lines appear as indented text after user lines in the colang history,
    e.g.:
        user "Show my transactions"
          user ask transactions
    """
    if not history:
        return None
    intent = None
    lines = history.splitlines()
    for index, line in enumerate(lines):
        if not line.startswith("user ") or index + 1 >= len(lines):
            continue
        nxt = lines[index + 1]
        if nxt.startswith("  ") and not nxt.strip().startswith('"'):
            intent = nxt.strip()
    return intent


def _masked(outcome, original):
    """Check if Presidio masked the text by comparing with original."""
    text = outcome.metadata.get("masked_text", original)
    if text == original:
        return "unchanged"
    return text


# Dialog flows defined in rails.co that we track in output
FLOW_RAILS = {"block advice", "block competitor comparison", "show transactions", "provide fd rates"}


async def describe(rails, result, user):
    """
    Generate a dry-run trace showing NeMo's execution pipeline:
    - Input rails (masking, self-check)
    - Dialog manager (intent matching, flow execution)
    - Tool execution
    - Output rails (self-check, masking)
    - Final response to user
    
    Args:
        rails: The NeMo RailsConfig instance
        result: The generation result from rails.generate_async()
        user: The original user message (pre-masking)
    
    Returns:
        Formatted trace string showing the complete execution flow
    """
    lines = []
    judges = {}
    tool_called = False
    flows = []

    # Parse activated rails to extract judges and flows
    retrieval_actions = []
    for rail in result.log.activated_rails:
        for action in rail.executed_actions:
            if action.action_name == "get_transactions_masked":
                tool_called = True
            # Track retrieval actions for Scenario 5
            if action.action_name in ("retrieve_documents", "filter_by_freshness", "format_fd_rates"):
                retrieval_actions.append(action.action_name)
            for call in action.llm_calls:
                if call.task in ("self_check_input", "self_check_output"):
                    judges[call.task] = _judge(call)
        if rail.name in FLOW_RAILS:
            step = rail.decisions[0] if rail.decisions else "matched"
            flows.append(f"{rail.name} → {step}")

    # INPUT RAILS
    flagged = judges.get("self_check_input")
    if flagged:
        verdict = "flagged" if flagged.lower().startswith("yes") else "no violation"
        lines.append(f"   input   self check input: {verdict} ({flagged})")

    masked = await mask_sensitive_data(source="input", text=user, config=rails.config)
    lines.append(f"   input   mask sensitive data: {_masked(masked, user)}")

    # DIALOG MANAGER
    intent = _last_intent(result.log.colang_history)
    if intent:
        lines.append(f"   dialog  intent: {intent}")
    if flows:
        lines.append(f"   dialog  flow: {'; '.join(flows)}")
    else:
        lines.append("   dialog  no flow for this intent; the model writes the reply")

    # RETRIEVAL RAILS (if any retrieval actions were executed)
    if retrieval_actions:
        lines.append(f"   retrieval: {', '.join(retrieval_actions)}")
    
    # TOOL EXECUTION
    lines.append(f"   tool called: {tool_called}")

    # OUTPUT RAILS
    if "self_check_output" in judges:
        verdict = "blocked" if judges["self_check_output"].lower().startswith("yes") else "allowed"
        lines.append(f"   output  self check output: {verdict} ({judges['self_check_output']})")
    else:
        lines.append("   output  not applied (the reply is a fixed line from rails.co)")

    lines.append(f"   user sees: {_reply_text(result)}")
    return "\n".join(lines)


async def run(rails, user, authenticated=False):
    """
    Execute a single user query through NeMo guardrails and print trace.
    
    Args:
        rails: The NeMo RailsConfig instance
        user: User message to process
        authenticated: Whether the user is authenticated (for stateful flows)
    """
    messages = [
        {"role": "context", "content": {"authenticated": authenticated}},
        {"role": "user", "content": user},
    ]
    result = await rails.generate_async(messages=messages, options=OPTIONS)
    print(await describe(rails, result, user))


async def main():
    """Run all five core scenarios demonstrating NeMo's guardrail capabilities."""
    rails = LLMRails(RailsConfig.from_path(str(CONFIG_DIR)))

    print("=" * 80)
    print("NeMo Guardrails Demo - Banking Agent with Retrieval Rails")
    print("=" * 80)
    print()
    
    for idx, scenario in enumerate(SCENARIOS, start=1):
        print(f"{scenario['title']}")
        print(f"   user: {scenario['user']}")
        await run(rails, scenario["user"], authenticated=scenario.get("authenticated", False))
        print(f"\n   📝 {scenario['note']}")
        print()
        if idx < len(SCENARIOS):
            print("-" * 80)
            print()

    print("=" * 80)
    print("Demo complete. All scenarios executed successfully.")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(main())
