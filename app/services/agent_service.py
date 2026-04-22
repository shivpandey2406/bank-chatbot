"""
Agent Service
Coordinates the multi-agent system.
"""

from typing import Dict, Any, Optional, List, Union
from datetime import datetime, timezone

from app.core.logging import get_logger
from app.agents.orchestrator import orchestrator, AgentState, AgentType

logger = get_logger(__name__)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class AgentService:
    """Coordinates the multi-agent orchestrator."""

    def __init__(self):
        self.orchestrator = orchestrator

    async def process_query(
        self, query: str, context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        logger.info(f"Processing query through agent service: {query[:80]}")
        try:
            # orchestrator.process_query is synchronous
            result = self.orchestrator.process_query(query, context)
            result["agent_service"] = {
                "orchestrator_used": True,
                "query_processed": True,
                "timestamp": _now_iso(),
            }
            return result
        except Exception as e:
            logger.exception("Error processing query in agent service", error=str(e))
            return {
                "success": False,
                "error": str(e),
                "response": "I apologize, but I encountered an error processing your request.",
            }

    async def get_agent_capabilities(self) -> Dict[str, Any]:
        try:
            from app.agents.account_agent import AccountAgent
            from app.agents.loan_agent import LoanAgent
            from app.agents.compliance_agent import ComplianceAgent
            from app.agents.notification_agent import NotificationAgent
            from app.agents.scheduling_agent import SchedulingAgent

            agents = {
                "account_agent": AccountAgent(),
                "loan_agent": LoanAgent(),
                "compliance_agent": ComplianceAgent(),
                "notification_agent": NotificationAgent(),
                "scheduling_agent": SchedulingAgent(),
            }
            capabilities = {}
            for name, agent in agents.items():
                try:
                    capabilities[name] = agent.get_capabilities()
                except Exception as e:
                    capabilities[name] = {"error": str(e)}

            return {
                "success": True,
                "capabilities": capabilities,
                "total_agents": len(agents),
                "timestamp": _now_iso(),
            }
        except Exception as e:
            logger.exception("Error getting agent capabilities", error=str(e))
            return {"success": False, "error": str(e), "capabilities": {}}

    async def get_system_status(self) -> Dict[str, Any]:
        try:
            orchestrator_status = {
                "initialized": self.orchestrator is not None,
                "graph_compiled": hasattr(self.orchestrator, "graph"),
                "ready": self.orchestrator is not None and hasattr(self.orchestrator, "graph"),
            }
            caps = await self.get_agent_capabilities()
            return {
                "success": True,
                "system_status": {
                    "orchestrator": orchestrator_status,
                    "agents_available": caps.get("total_agents", 0),
                    "system_ready": orchestrator_status["ready"],
                    "timestamp": _now_iso(),
                },
                "capabilities": caps.get("capabilities", {}),
            }
        except Exception as e:
            logger.exception("Error getting system status", error=str(e))
            return {"success": False, "error": str(e)}
