"""
Scheduling Agent
Handles appointment and meeting scheduling with LLM-powered responses.
"""

from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from enum import Enum

from app.core.logging import get_logger

logger = get_logger(__name__)


class AppointmentType(str, Enum):
    ACCOUNT_REVIEW = "account_review"
    LOAN_CONSULTATION = "loan_consultation"
    MORTGAGE_APPLICATION = "mortgage_application"
    FINANCIAL_ADVISORY = "financial_advisory"
    GENERAL_INQUIRY = "general_inquiry"


SYSTEM_PROMPT = """You are a specialized scheduling assistant for a banking system. You help with:
- Booking new appointments (Account Review 30min, Loan Consultation 45min,
  Mortgage Application 60min, Financial Advisory 60min, General Inquiry 15min)
- Rescheduling existing appointments
- Canceling appointments
- Checking availability
- Viewing upcoming appointments

Business hours: Mon-Fri 9AM-5PM, Sat 9AM-1PM, Sun closed.
Ask for appointment type, preferred date/time, and contact information."""


class SchedulingAgent:
    def __init__(self):
        self.name = "scheduling_agent"
        self.description = "Handles appointment scheduling, rescheduling, and cancellations"

    def process(self, query: str, context: Optional[Dict[str, Any]] = None) -> str:
        from app.agents.orchestrator import _llm_generate
        return _llm_generate(SYSTEM_PROMPT, query)

    async def process_query(self, query: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        return {"response": self.process(query, context), "metadata": {"query_type": "scheduling"}}

    def get_capabilities(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "capabilities": ["booking", "rescheduling", "cancellation",
                             "availability_check", "appointment_info", "reminders"],
            "appointment_types": [t.value for t in AppointmentType],
            "requires_authentication": False,
        }
