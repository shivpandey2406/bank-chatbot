"""
Account Agent
Handles account-related queries with LLM-powered responses.
"""

from typing import Dict, Any, Optional

from app.core.logging import get_logger

logger = get_logger(__name__)

SYSTEM_PROMPT = """You are a specialized banking account assistant. You help customers with:
- Checking account balances
- Viewing transaction history
- Accessing account statements
- Updating account information
- Account settings and preferences

Provide helpful, accurate, and professional responses. If you need more information
from the customer, ask clarifying questions. Always prioritize security — never reveal
sensitive account details without proper verification."""


class AccountAgent:
    def __init__(self):
        self.name = "account_agent"
        self.description = "Handles account-related queries including balances, transactions, and account details"

    def process(self, query: str, context: Optional[Dict[str, Any]] = None) -> str:
        from app.agents.orchestrator import _llm_generate
        return _llm_generate(SYSTEM_PROMPT, query)

    async def process_query(self, query: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        return {"response": self.process(query, context), "metadata": {"query_type": "account"}}

    def get_capabilities(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "capabilities": ["balance_inquiry", "transaction_history", "statement_request", "account_info"],
            "requires_authentication": True,
        }
