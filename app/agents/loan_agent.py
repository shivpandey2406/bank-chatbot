"""
Loan Agent
Handles loan-related queries with LLM-powered responses.
"""

from typing import Dict, Any, Optional

from app.core.logging import get_logger

logger = get_logger(__name__)

SYSTEM_PROMPT = """You are a specialized banking loan assistant. You help customers with:
- Loan applications (personal, auto, mortgage, business)
- Loan payment information and schedules
- Interest rate inquiries
- Loan status checks
- Refinancing options
- Mortgage products

Provide helpful, accurate, and professional responses about loan products and processes."""


class LoanAgent:
    def __init__(self):
        self.name = "loan_agent"
        self.description = "Handles loan-related queries including applications, payments, and loan products"

    def process(self, query: str, context: Optional[Dict[str, Any]] = None) -> str:
        from app.agents.orchestrator import _llm_generate
        return _llm_generate(SYSTEM_PROMPT, query)

    async def process_query(self, query: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        return {"response": self.process(query, context), "metadata": {"query_type": "loan"}}

    def get_capabilities(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "capabilities": ["loan_application", "payment_assistance", "interest_rate_info",
                             "loan_status", "refinance", "mortgage"],
            "requires_authentication": False,
        }
