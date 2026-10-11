"""Custom Actions for NeMo Banking Agent

This module defines custom actions that can be invoked by dialog flows in rails.co.
Actions are Python functions decorated with @action that NeMo can call during
conversation flow execution.

Available Actions:
    - get_transactions_masked: Returns recent transaction history with sensitive
                               data already masked (if needed by output rails)

Note: The banking agent is described as having three tools:
    - verify_otp: Would set $authenticated flag (not implemented in this demo)
    - get_transactions: Implemented as get_transactions_masked
    - transfer_money: Not implemented (would require authentication check)

In this demo, $authenticated is set via the message context rather than 
through verify_otp execution.
"""

from nemoguardrails.actions import action


@action(name="get_transactions_masked")
async def get_transactions_masked():
    """
    Retrieve the user's recent transaction history.
    
    This action is called by the 'show transactions' flow in rails.co,
    but only after verifying $authenticated is True.
    
    In a production system, this would:
    1. Fetch real transaction data from a banking API
    2. Apply masking to sensitive fields (account numbers, full amounts)
    3. Return formatted transaction list
    
    Returns:
        str: Formatted transaction history with dates, descriptions, and amounts
    
    Example output:
        "01 Oct  Grocery  ₹1,240\n03 Oct  Transfer  ₹5,000"
    """
    # Mock transaction data for demonstration purposes
    return "01 Oct  Grocery  ₹1,240\n03 Oct  Transfer  ₹5,000"
