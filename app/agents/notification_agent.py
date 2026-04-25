"""
Notification Agent
Handles notification-related queries with LLM-powered responses.
When an actionable intent is detected (send email, post to Slack),
executes the real MCP tool using stored OAuth tokens.
"""

from typing import Dict, Any, Optional
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
        from app.services.tool_router import detect_tool_intent, execute_tool_sync

        intent = detect_tool_intent(query)
        if intent and intent["tool"] in ("send_email", "send_slack"):
            if intent.get("needs_details"):
                from app.agents.orchestrator import _llm_generate
                return _llm_generate(SYSTEM_PROMPT, query)

            logger.info("NotificationAgent executing MCP tool", tool=intent["tool"])
            result = execute_tool_sync(intent)

            if result.get("success"):
                if intent["tool"] == "send_email":
                    return f"Email sent successfully. Message ID: {result.get('id', 'N/A')}"
                return "Slack message sent successfully."
            else:
                return f"Action failed: {result.get('error', 'Unknown error')}"

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
