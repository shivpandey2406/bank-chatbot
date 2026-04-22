"""
Compliance Agent
Handles compliance-related queries with LLM-powered responses.
"""

from typing import Dict, Any, Optional

from app.core.logging import get_logger

logger = get_logger(__name__)

SYSTEM_PROMPT = """You are a specialized banking compliance assistant. You help with:
- KYC (Know Your Customer) requirements and verification
- AML (Anti-Money Laundering) procedures
- Fraud prevention and reporting
- Audit information and processes
- Banking regulations (BSA, Dodd-Frank, TILA, FCRA, PATRIOT Act, GDPR/CCPA)
- Regulatory reporting (CTR, SAR, Call Reports)

Provide accurate compliance guidance. Always recommend consulting with a compliance
officer for specific regulatory decisions."""


class ComplianceAgent:
    def __init__(self):
        self.name = "compliance_agent"
        self.description = "Handles compliance-related queries including regulations, policies, and audit information"

    def process(self, query: str, context: Optional[Dict[str, Any]] = None) -> str:
        from app.agents.orchestrator import _llm_generate
        return _llm_generate(SYSTEM_PROMPT, query)

    async def process_query(self, query: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        return {"response": self.process(query, context), "metadata": {"query_type": "compliance"}}

    def get_capabilities(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "capabilities": ["kyc", "aml", "fraud", "audit", "regulation", "reporting"],
            "requires_authentication": False,
        }
