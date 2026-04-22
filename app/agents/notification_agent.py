"""
Notification Agent
Handles notification-related queries with LLM-powered responses.
"""

from typing import Dict, Any, Optional, List
from enum import Enum

from app.core.logging import get_logger

logger = get_logger(__name__)


class NotificationType(str, Enum):
    EMAIL = "email"
    SMS = "sms"
    PUSH = "push"
    SLACK = "slack"


SYSTEM_PROMPT = """You are a specialized notification assistant for a banking system. You help with:
- Sending emails to customers
- Sending SMS messages
- Sending Slack messages to team channels
- Sending push notifications
- Scheduling notifications for later delivery

When the user wants to send a notification, ask for the required details:
recipient, subject/title, and message content. Confirm before sending."""


class NotificationAgent:
    def __init__(self):
        self.name = "notification_agent"
        self.description = "Handles sending notifications via email, SMS, push, and Slack"

    def process(self, query: str, context: Optional[Dict[str, Any]] = None) -> str:
        from app.agents.orchestrator import _llm_generate
        return _llm_generate(SYSTEM_PROMPT, query)

    async def process_query(self, query: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        return {"response": self.process(query, context), "metadata": {"query_type": "notification"}}

    def get_capabilities(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "capabilities": ["email", "sms", "slack", "push", "scheduled", "templates"],
            "requires_authentication": False,
        }
