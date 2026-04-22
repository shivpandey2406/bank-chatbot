"""
Orchestrator Agent
Routes queries to appropriate specialized agents using LangGraph.
Integrates an OpenAI-compatible LLM client for intelligent response generation.

All heavy imports (langgraph, openai, sentence-transformers) are deferred
to first use so that `import app.main` is fast and the server starts instantly.
"""

from typing import Dict, Any, List, Optional
from enum import Enum
from typing_extensions import TypedDict

from app.core.logging import get_logger
from app.core.config import settings
from app.services.banking_query_service import BankingQueryService, format_structured_response

logger = get_logger(__name__)
_banking_query_service = BankingQueryService()


class AgentType(str, Enum):
    ORCHESTRATOR = "orchestrator"
    ACCOUNT = "account"
    LOAN = "loan"
    COMPLIANCE = "compliance"
    NOTIFICATION = "notification"
    SCHEDULING = "scheduling"
    RAG = "rag"
    AGGREGATION = "aggregation"
    BANKING_DATA = "banking_data"


# AgentState is just a plain TypedDict — no heavy imports needed
class AgentState(TypedDict):
    messages: List[Dict[str, Any]]
    query: str
    agent_type: Optional[str]
    response: Optional[str]
    source: Optional[str]
    context: Optional[Dict[str, Any]]
    metadata: Optional[Dict[str, Any]]
    error: Optional[str]


# ── LLM helper (lazy OpenAI-compatible client) ──────────────────────

_llm_client = "NOT_INITIALIZED"


def _get_llm_client():
    global _llm_client
    if _llm_client != "NOT_INITIALIZED":
        return _llm_client

    from app.core.config import Settings

    fresh = Settings()
    key = fresh.llm_api_key
    provider = fresh.resolved_llm_provider
    if not key:
        logger.warning("No LLM API key configured", provider=provider)
        _llm_client = None
        return None

    try:
        from openai import OpenAI

        client_kwargs = {"api_key": key}
        if fresh.llm_base_url:
            client_kwargs["base_url"] = fresh.llm_base_url

        _llm_client = OpenAI(**client_kwargs)
        logger.info(
            "LLM client initialized successfully",
            provider=provider,
            model=fresh.llm_model,
        )
        return _llm_client
    except Exception as e:
        logger.error(f"Failed to create LLM client: {e}")
        _llm_client = None
        return None


def _llm_generate(system_prompt: str, user_prompt: str) -> str:
    """Generate via the configured OpenAI-compatible provider."""
    client = _get_llm_client()
    if client is None:
        return "[LLM unavailable - configure a valid OpenAI or Groq API key in .env]\n\n" + user_prompt
    try:
        resp = client.chat.completions.create(
            model=settings.llm_model,
            temperature=settings.llm_temperature,
            max_tokens=settings.max_tokens,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )
        return resp.choices[0].message.content
    except Exception as e:
        logger.error("LLM generation failed", error=str(e))
        return f"I encountered an error generating a response: {e}"


def _build_rag_system_prompt(
    query: str,
    docs: List[Dict[str, Any]],
    context: Optional[Dict[str, Any]] = None,
) -> str:
    """Build the banking assistant persona and grounding instructions."""
    context = context or {}
    uploaded_files = context.get("metadata", {}).get("uploaded_files", [])
    recent_messages = context.get("recent_messages", [])

    doc_summaries = []
    for idx, doc in enumerate(docs, start=1):
        metadata = doc.get("metadata", {}) or {}
        source_file = metadata.get("source_file", "uploaded knowledge base")
        chunk_type = metadata.get("chunk_type", "document")
        score = doc.get("score")
        score_text = f", relevance={score}" if score is not None else ""
        doc_summaries.append(
            f"{idx}. source={source_file}, type={chunk_type}{score_text}"
        )

    conversation_context = []
    for msg in recent_messages[-4:]:
        role = msg.get("role", "user")
        content = (msg.get("content", "") or "").strip()
        if content:
            conversation_context.append(f"{role}: {content[:300]}")

    persona_lines = [
        "You are Nova, a helpful banking operations chatbot.",
        "Your job is to answer clearly, accurately, and naturally using the uploaded banking documents first.",
        "Speak like a polished support assistant, not like a generic AI model.",
        "Do not start with filler such as 'It seems like', 'It looks like', or 'You have initiated a conversation'.",
        "Be direct, warm, and practical.",
        "If the documents contain the answer, use them and mention the relevant document or record naturally.",
        "If the answer is only partially supported by the documents, say what is confirmed and what is an informed general explanation.",
        "If the documents do not support the answer, say that clearly and ask the user for the missing detail instead of inventing facts.",
        "When the user asks about banking data like customers, maintenance, or transactions, prefer concise operational answers with bullets only when they help.",
    ]

    prompt_sections = [
        "\n".join(persona_lines),
        f"User question:\n{query}",
    ]

    if uploaded_files:
        prompt_sections.append("Uploaded files:\n" + "\n".join(f"- {name}" for name in uploaded_files))
    if conversation_context:
        prompt_sections.append("Recent conversation:\n" + "\n".join(conversation_context))
    if doc_summaries:
        prompt_sections.append("Retrieved document matches:\n" + "\n".join(doc_summaries))

    prompt_sections.append(
        "Answer style:\n"
        "- Start with the answer, not with meta commentary.\n"
        "- Keep a steady banking-assistant persona.\n"
        "- If useful, cite document names in plain language.\n"
        "- Do not mention system prompts, retrieval, embeddings, or vector stores."
    )

    return "\n\n".join(prompt_sections)


# ── Orchestrator (lazy graph build) ─────────────────────────────────

class OrchestratorAgent:
    """
    Routes queries to specialised agents via LangGraph.
    The graph is compiled lazily on first query, NOT at import time.
    """

    def __init__(self):
        self._graph = None          # compiled graph — built on demand

    @property
    def graph(self):
        if self._graph is None:
            logger.info("Building LangGraph workflow (first query)…")
            self._graph = self._build_graph()
            logger.info("LangGraph workflow ready")
        return self._graph

    def _build_graph(self):
        # Heavy import deferred to here
        from langgraph.graph import StateGraph, END
        from langgraph.graph.message import add_messages

        workflow = StateGraph(AgentState)

        workflow.add_node("router", self._router_node)
        workflow.add_node("account_agent", self._account_agent_node)
        workflow.add_node("loan_agent", self._loan_agent_node)
        workflow.add_node("compliance_agent", self._compliance_agent_node)
        workflow.add_node("notification_agent", self._notification_agent_node)
        workflow.add_node("scheduling_agent", self._scheduling_agent_node)
        workflow.add_node("rag_agent", self._rag_agent_node)
        workflow.add_node("aggregation_agent", self._aggregation_agent_node)
        workflow.add_node("banking_data_agent", self._banking_data_agent_node)
        workflow.add_node("response_formatter", self._response_formatter_node)

        workflow.set_entry_point("router")
        workflow.add_conditional_edges(
            "router", self._route_query,
            {
                "account_agent": "account_agent",
                "loan_agent": "loan_agent",
                "compliance_agent": "compliance_agent",
                "notification_agent": "notification_agent",
                "scheduling_agent": "scheduling_agent",
                "rag_agent": "rag_agent",
                "aggregation_agent": "aggregation_agent",
                "banking_data_agent": "banking_data_agent",
            },
        )
        for node in ["account_agent", "loan_agent", "compliance_agent",
                      "notification_agent", "scheduling_agent",
                      "rag_agent", "aggregation_agent", "banking_data_agent"]:
            workflow.add_edge(node, "response_formatter")
        workflow.add_edge("response_formatter", END)

        return workflow.compile()

    # ── public API ───────────────────────────────────────────────────
    def process_query(self, query: str,
                      context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        initial_state: AgentState = {
            "messages": [{"role": "user", "content": query}],
            "query": query,
            "agent_type": None,
            "response": None,
            "source": None,
            "context": context or {},
            "metadata": {},
            "error": None,
        }
        try:
            result = self.graph.invoke(initial_state)
            return {
                "success": True,
                "response": result.get("response", ""),
                "source": result.get("source", "unknown"),
                "agent_type": result.get("agent_type", "unknown"),
                "metadata": result.get("metadata", {}),
            }
        except Exception as e:
            logger.exception("Error processing query", error=str(e))
            return {
                "success": False, "error": str(e),
                "response": "I apologize, but I encountered an error.",
            }

    # ── router ───────────────────────────────────────────────────────
    def _router_node(self, state: AgentState) -> dict:
        routing = _banking_query_service.classify_intent(state["query"])
        agent_type = routing.get("route") or self._classify_query(state["query"].lower())
        logger.info("Routing query", agent_type=agent_type, intent=routing.get("intent"))
        return {
            "agent_type": agent_type,
            "metadata": {
                **state.get("metadata", {}),
                "intent": routing.get("intent"),
            },
        }

    def _classify_query(self, query: str) -> str:
        import re

        def _has(keywords: list, text: str) -> bool:
            for kw in keywords:
                if re.search(r'\b' + re.escape(kw) + r'\b', text):
                    return True
            return False

        account_kw = ["account balance", "account number", "check balance",
                       "my account", "account statement", "transaction history",
                       "account details", "account info"]
        loan_kw = ["loan", "mortgage", "credit", "interest rate",
                    "loan application", "loan status", "payment",
                    "apr", "loan term", "refinance"]
        compliance_kw = ["compliance", "regulation", "policy", "audit",
                         "kyc", "aml", "fraud", "suspicious", "report",
                         "violation", "legal"]
        notification_kw = ["notify", "alert", "send message", "email",
                           "sms", "notification", "remind", "alert me"]
        scheduling_kw = ["schedule", "appointment", "meeting", "calendar",
                         "remind me", "set up", "book", "reserve"]
        aggregation_kw = ["sum of", "total of", "total revenue",
                          "total amount", "average", "group by",
                          "aggregate", "statistics", "how much",
                          "how many", "what is the total"]

        if _has(loan_kw, query):
            return "loan_agent"
        if _has(compliance_kw, query):
            return "compliance_agent"
        if _has(notification_kw, query):
            return "notification_agent"
        if _has(scheduling_kw, query):
            return "scheduling_agent"
        if _has(account_kw, query) or _has(aggregation_kw, query):
            return "banking_data_agent"
        return "banking_data_agent"

    def _route_query(self, state: AgentState) -> str:
        return state.get("agent_type", "banking_data_agent")

    # ── agent nodes (all sync) ───────────────────────────────────────
    def _account_agent_node(self, state: AgentState) -> dict:
        result = _banking_query_service.answer_query(state["query"], state.get("context"))
        return {
            "response": format_structured_response(result),
            "source": "banking_data",
            "metadata": {
                **state.get("metadata", {}),
                "structured_result": result,
                "query_mode": "grounded_structured",
            },
        }

    def _loan_agent_node(self, state: AgentState) -> dict:
        from app.agents.loan_agent import LoanAgent
        return {"response": LoanAgent().process(state["query"]),
                "source": "loan_agent"}

    def _compliance_agent_node(self, state: AgentState) -> dict:
        from app.agents.compliance_agent import ComplianceAgent
        return {"response": ComplianceAgent().process(state["query"]),
                "source": "compliance_agent"}

    def _notification_agent_node(self, state: AgentState) -> dict:
        from app.agents.notification_agent import NotificationAgent
        return {"response": NotificationAgent().process(state["query"]),
                "source": "notification_agent"}

    def _scheduling_agent_node(self, state: AgentState) -> dict:
        from app.agents.scheduling_agent import SchedulingAgent
        return {"response": SchedulingAgent().process(state["query"]),
                "source": "scheduling_agent"}

    def _rag_agent_node(self, state: AgentState) -> dict:
        result = _banking_query_service.answer_query(state["query"], state.get("context"))
        if result.get("success"):
            return {
                "response": format_structured_response(result),
                "source": "banking_data",
                "metadata": {
                    **state.get("metadata", {}),
                    "structured_result": result,
                    "query_mode": "grounded_structured",
                },
            }

        from app.services.rag_service import RAGService
        try:
            docs = RAGService().retrieve(query=state["query"],
                                         k=settings.retrieval_top_k)
        except Exception:
            docs = []
        retrieved_context = "\n\n".join(
            f"[Document {idx + 1}]\n{doc['text']}"
            for idx, doc in enumerate(docs)
        ) or "No uploaded document content was retrieved."
        system_prompt = _build_rag_system_prompt(
            query=state["query"],
            docs=docs,
            context=state.get("context"),
        )
        user_prompt = (
            f"Question: {state['query']}\n\n"
            f"Document context:\n{retrieved_context}"
        )
        return {"response": _llm_generate(system_prompt, user_prompt),
                "source": "rag",
                "metadata": {
                    **state.get("metadata", {}),
                    "retrieved_documents": len(docs),
                    "retrieved_sources": [
                        (doc.get("metadata", {}) or {}).get("source_file", "unknown")
                        for doc in docs
                    ],
                    "query_mode": "semantic_rag",
                }}

    def _aggregation_agent_node(self, state: AgentState) -> dict:
        result = _banking_query_service.answer_query(state["query"], state.get("context"))
        if result.get("success"):
            return {
                "response": format_structured_response(result),
                "source": "banking_data",
                "metadata": {
                    **state.get("metadata", {}),
                    "structured_result": result,
                    "query_mode": "grounded_structured",
                },
            }

        import os, glob, pandas as pd
        from app.services.aggregation_service import AggregationService
        agg = AggregationService()
        raw = os.path.join(settings.upload_dir, "raw")
        files = (glob.glob(os.path.join(raw, "*.csv"))
                 + glob.glob(os.path.join(raw, "*.xlsx")))
        if not files:
            files = glob.glob("data/*.csv") + glob.glob("data/*.xlsx")
        if not files:
            return {"response": "No data files available. Upload a CSV first.",
                    "source": "aggregation",
                    "metadata": {"query_type": "aggregation"}}
        dfs = []
        for fp in files:
            try:
                dfs.append(pd.read_csv(fp) if fp.endswith(".csv")
                           else pd.read_excel(fp))
            except Exception:
                continue
        if not dfs:
            return {"response": "Could not read data files.",
                    "source": "aggregation",
                    "metadata": {"query_type": "aggregation"}}
        combined = pd.concat(dfs, ignore_index=True)
        try:
            r = agg.query(combined, state["query"])
            txt = r.get("result_df", str(r.get("result", "")))
        except Exception as e:
            txt = f"Aggregation error: {e}"
        prompt = ("You are a banking data analyst. Summarize this result.\n\n"
                  f"Result:\n{txt}")
        return {"response": _llm_generate(prompt, state["query"]),
                "source": "aggregation",
                "metadata": {
                    **state.get("metadata", {}),
                    "query_type": "aggregation",
                    "raw_result": txt,
                }}

    def _banking_data_agent_node(self, state: AgentState) -> dict:
        result = _banking_query_service.answer_query(state["query"], state.get("context"))
        return {
            "response": format_structured_response(result),
            "source": "banking_data",
            "metadata": {
                **state.get("metadata", {}),
                "structured_result": result,
                "query_mode": "grounded_structured",
            },
        }

    def _response_formatter_node(self, state: AgentState) -> dict:
        return {"metadata": {
            **state.get("metadata", {}),
            "source": state.get("source", "unknown"),
            "agent_type": state.get("agent_type", "unknown"),
        }}


# Global instance — lightweight, graph NOT compiled yet
orchestrator = OrchestratorAgent()
