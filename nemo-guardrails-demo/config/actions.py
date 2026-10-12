"""Custom Actions for NeMo Banking Agent

This module defines custom actions that can be invoked by dialog flows in rails.co.
Actions are Python functions decorated with @action that NeMo can call during
conversation flow execution.

Available Actions:
    - get_transactions_masked: Returns recent transaction history with sensitive
                               data already masked (if needed by output rails)
    - retrieve_documents: Simulates knowledge base retrieval (Scenario 5)
    - filter_by_freshness: Retrieval rail that filters documents by age and permissions
    - format_fd_rates: Extracts FD rates from filtered documents

Note: The banking agent is described as having three tools:
    - verify_otp: Would set $authenticated flag (not implemented in this demo)
    - get_transactions: Implemented as get_transactions_masked
    - transfer_money: Not implemented (would require authentication check)

In this demo, $authenticated is set via the message context rather than 
through verify_otp execution.
"""

from datetime import datetime, timedelta
from typing import List, Dict

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


# ============================================================================
# Scenario 5: Retrieval Rails - Knowledge Base Actions
# ============================================================================

@action(name="retrieve_documents")
async def retrieve_documents(query: str) -> List[Dict]:
    """
    Simulate retrieval from knowledge base.
    
    In production, this would call your vector database (Pinecone, Weaviate,
    Chroma, etc.) or document store. For this demo, we return mock documents
    with metadata including publish_date and document_type.
    
    Args:
        query: Search query string
    
    Returns:
        List of document dictionaries with content and metadata
    """
    # Mock knowledge base with mixed fresh, stale, and restricted documents
    mock_kb = [
        {
            "content": "Fixed Deposit rates: 1-year: 7.2%, 2-year: 7.5%, 5-year: 7.8%",
            "publish_date": "2026-10-01",
            "document_type": "public",
            "source": "product_catalog_oct_2026.pdf"
        },
        {
            "content": "Fixed Deposit rates: 1-year: 6.5%, 2-year: 6.8%, 5-year: 7.0%",
            "publish_date": "2023-06-15",  # Outdated! Over 90 days old
            "document_type": "public",
            "source": "product_catalog_2023.pdf"
        },
        {
            "content": "Internal analysis: Competitor HDFC offers 7.5% on 1-year FDs",
            "publish_date": "2026-09-20",
            "document_type": "internal-only",  # Restricted! Should be filtered
            "source": "competitive_analysis.pdf"
        }
    ]
    
    # Simple keyword matching (production would use vector similarity)
    relevant_docs = [doc for doc in mock_kb if "deposit" in doc["content"].lower() or "fd" in query.lower()]
    return relevant_docs


@action(name="filter_by_freshness")
async def filter_by_freshness(docs: List[Dict], max_age_days: int = 90) -> List[Dict]:
    """
    Retrieval rail: Filter documents by age and permissions.
    
    This is where the retrieval guardrail activates - BEFORE the LLM sees
    the retrieved content. Filters out:
    1. Documents older than max_age_days
    2. Documents not in allowed_document_types
    3. Documents containing blocked keywords
    
    Args:
        docs: List of retrieved documents
        max_age_days: Maximum document age in days (default: 90)
    
    Returns:
        Filtered list of documents that pass all retrieval rails
    """
    cutoff_date = datetime.now() - timedelta(days=max_age_days)
    filtered = []
    
    for doc in docs:
        doc_date = datetime.strptime(doc["publish_date"], "%Y-%m-%d")
        age_days = (datetime.now() - doc_date).days
        
        # Retrieval Rail 1: Age check
        if doc_date < cutoff_date:
            print(f"⚠️  RETRIEVAL RAIL: Rejected outdated document: {doc['source']} (age: {age_days} days)")
            continue
        
        # Retrieval Rail 2: Permission check
        if doc["document_type"] not in ["public", "customer-facing"]:
            print(f"⚠️  RETRIEVAL RAIL: Rejected restricted document: {doc['source']} (type: {doc['document_type']})")
            continue
        
        # Retrieval Rail 3: Blocked keyword check
        blocked_keywords = ["internal-only", "competitor", "hdfc", "icici"]
        if any(keyword in doc["content"].lower() for keyword in blocked_keywords):
            print(f"⚠️  RETRIEVAL RAIL: Rejected document with blocked keywords: {doc['source']}")
            continue
        
        # Document passed all retrieval rails
        filtered.append(doc)
    
    return filtered


@action(name="format_fd_rates")
async def format_fd_rates(docs: List[Dict]) -> str:
    """
    Extract and format FD rates from filtered documents.
    
    Args:
        docs: List of filtered documents (post-retrieval rails)
    
    Returns:
        Formatted string of FD rates
    """
    if not docs:
        return "No current rate information available."
    
    # Use most recent document
    latest_doc = sorted(docs, key=lambda d: d["publish_date"], reverse=True)[0]
    
    # Extract rates (simplified - production would use better parsing)
    content = latest_doc["content"]
    if "Fixed Deposit rates:" in content:
        return content.split("Fixed Deposit rates:")[1].strip()
    
    return content
