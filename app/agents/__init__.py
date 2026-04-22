"""
Agents Package — imports are lazy to avoid slow startup.
Use: from app.agents.orchestrator import orchestrator
"""

from app.agents.account_agent import AccountAgent
from app.agents.loan_agent import LoanAgent
from app.agents.compliance_agent import ComplianceAgent
from app.agents.notification_agent import NotificationAgent
from app.agents.scheduling_agent import SchedulingAgent

__all__ = [
    "AccountAgent", "LoanAgent", "ComplianceAgent",
    "NotificationAgent", "SchedulingAgent",
]
