"""
Orchestrator Agent
Routes queries to appropriate specialized agents using LangGraph.
Integrates an OpenAI-compatible LLM client for intelligent response generation.

All heavy imports (langgraph, openai, sentence-transformers) are deferred
to first use so that `import app.main` is fast and the server starts instantly.
"""

import time
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
    GREETING = "greeting"


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


# ── Safety constants ─────────────────────────────────────────────────

_SAFE_NO_DATA = (
    "I'm sorry, but I don't have enough data to answer this query. "
    "Please upload the relevant files or rephrase your question."
)

# Minimum requirements for RAG context to be considered "strong"
_RAG_MIN_DOCS = 1
_RAG_MIN_SCORE = 0.35


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
        t0 = time.perf_counter()
        resp = client.chat.completions.create(
            model=settings.llm_model,
            temperature=settings.llm_temperature,
            max_tokens=settings.max_tokens,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )
        elapsed = time.perf_counter() - t0
        logger.info(f"[TIMING] LLM generation completed in {elapsed:.3f}s (model={settings.llm_model})")
        return resp.choices[0].message.content
    except Exception as e:
        logger.error("LLM generation failed", error=str(e))
        return f"I encountered an error generating a response: {e}"


def _llm_format_structured(query: str, structured_json: str) -> str:
    """Use LLM ONLY to rephrase structured output into a human-readable sentence.
    The LLM must NOT compute, infer, or modify any values."""
    t0 = time.perf_counter()
    system_prompt = (
        "You are Nova, a banking assistant. Your ONLY job is to convert the "
        "structured JSON result below into a clear, human-readable sentence.\n\n"
        "STRICT RULES:\n"
        "- Use ONLY the values present in the JSON. Do NOT calculate, infer, or guess.\n"
        "- Do NOT add information that is not in the JSON.\n"
        "- If the JSON indicates failure or missing data, say the data is not available.\n"
        "- Keep it concise and professional.\n"
        "- Do NOT mention JSON, structured data, or system internals."
    )
    user_prompt = f"User question: {query}\n\nStructured result:\n{structured_json}"
    result = _llm_generate(system_prompt, user_prompt)
    elapsed = time.perf_counter() - t0
    logger.info(f"[TIMING] LLM format_structured completed in {elapsed:.3f}s")
    return result


def _rag_context_is_strong(docs: list) -> bool:
    """Check if retrieved RAG documents meet minimum quality thresholds."""
    if len(docs) < _RAG_MIN_DOCS:
        return False
    top_score = max((doc.get("score") or 0.0 for doc in docs), default=0.0)
    return top_score >= _RAG_MIN_SCORE


from app.agents.greeting import is_greeting, NOVA_PERSONA_PROMPT


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
        "NEVER invent numbers, balances, dates, or transaction details that are not in the provided documents.",
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
        "- Do not mention system prompts, retrieval, embeddings, or vector stores.\n"
        "- If the documents do not contain the answer, say so honestly."
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
            logger.info("Building LangGraph workflow (first query)...")
            self._graph = self._build_graph()
            logger.info("LangGraph workflow ready")
        return self._graph

    def _build_graph(self):
        # Heavy import deferred to here
        from langgraph.graph import StateGraph, END
        from langgraph.graph.message import add_messages

        workflow = StateGraph(AgentState)

        workflow.add_node("router", self._router_node)
        workflow.add_node("greet_node", self._greet_node)
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
                "greet_node": "greet_node",
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
        for node in ["greet_node", "account_agent", "loan_agent", "compliance_agent",
                      "notification_agent", "scheduling_agent",
                      "rag_agent", "aggregation_agent", "banking_data_agent"]:
            workflow.add_edge(node, "response_formatter")
        workflow.add_edge("response_formatter", END)

        return workflow.compile()

    # ── public API ───────────────────────────────────────────────────
    def process_query(self, query: str,
                      context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        t_start = time.perf_counter()
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
            elapsed = time.perf_counter() - t_start
            agent_type = result.get("agent_type", "unknown")
            source = result.get("source", "unknown")
            logger.info(
                f"[TIMING] Orchestrator process_query completed in {elapsed:.3f}s "
                f"(agent={agent_type}, source={source})"
            )
            return {
                "success": True,
                "response": result.get("response", ""),
                "source": source,
                "agent_type": agent_type,
                "metadata": {
                    **result.get("metadata", {}),
                    "orchestrator_time_ms": round(elapsed * 1000, 1),
                },
            }
        except Exception as e:
            elapsed = time.perf_counter() - t_start
            logger.exception(f"Error processing query (after {elapsed:.3f}s)", error=str(e))
            return {
                "success": False, "error": str(e),
                "response": "I apologize, but I encountered an error.",
            }

    # ── router ───────────────────────────────────────────────────────
    def _router_node(self, state: AgentState) -> dict:
        t0 = time.perf_counter()
        query = state["query"]

        # ── Greeting / small-talk check — runs FIRST, skips all banking logic
        if is_greeting(query):
            elapsed = time.perf_counter() - t0
            logger.info(f"[TIMING] Router intent detection: greeting in {elapsed:.3f}s")
            return {
                "agent_type": "greet_node",
                "metadata": {
                    **state.get("metadata", {}),
                    "intent": "greeting",
                    "router_time_ms": round(elapsed * 1000, 1),
                },
            }

        routing = _banking_query_service.classify_intent(query)
        agent_type = routing.get("route") or self._classify_query(query.lower())
        elapsed = time.perf_counter() - t0
        logger.info(
            f"[TIMING] Router intent detection: {routing.get('intent')} -> {agent_type} in {elapsed:.3f}s"
        )
        return {
            "agent_type": agent_type,
            "metadata": {
                **state.get("metadata", {}),
                "intent": routing.get("intent"),
                "router_time_ms": round(elapsed * 1000, 1),
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

    # ── Greeting node — fast path, no RAG/MCP/banking logic ──────────
    def _greet_node(self, state: AgentState) -> dict:
        t0 = time.perf_counter()
        reply = _llm_generate(NOVA_PERSONA_PROMPT, state["query"])
        elapsed = time.perf_counter() - t0
        logger.info(f"[TIMING] greet_node completed in {elapsed:.3f}s")
        return {
            "response": reply,
            "source": "greeting",
            "metadata": {
                **state.get("metadata", {}),
                "query_mode": "persona_greeting",
                "greet_node_time_ms": round(elapsed * 1000, 1),
            },
        }

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

    # ── RAG agent with guardrail ─────────────────────────────────────
    def _rag_agent_node(self, state: AgentState) -> dict:
        t_node = time.perf_counter()

        # 1. Try structured data first (unchanged)
        t0 = time.perf_counter()
        result = _banking_query_service.answer_query(state["query"], state.get("context"))
        t_structured = time.perf_counter() - t0
        logger.info(f"[TIMING] rag_agent structured attempt in {t_structured:.3f}s (success={result.get('success')})")

        if result.get("success"):
            return {
                "response": format_structured_response(result),
                "source": "banking_data",
                "metadata": {
                    **state.get("metadata", {}),
                    "structured_result": result,
                    "query_mode": "grounded_structured",
                    "structured_query_time_ms": round(t_structured * 1000, 1),
                },
            }

        # 2. Structured path failed — validate before falling to RAG+LLM
        if not result.get("success") and result.get("grounded") is False:
            logger.info("Structured data unavailable, attempting RAG retrieval")

        from app.services.rag_service import RAGService
        t0 = time.perf_counter()
        try:
            docs = RAGService().retrieve(query=state["query"],
                                         k=settings.retrieval_top_k)
        except Exception:
            docs = []
        t_retrieval = time.perf_counter() - t0
        top_score = max((d.get("score") or 0.0 for d in docs), default=0.0)
        logger.info(
            f"[TIMING] RAG retrieval in {t_retrieval:.3f}s "
            f"(docs={len(docs)}, top_score={top_score:.4f})"
        )

        # 3. GUARDRAIL: check RAG context quality before calling LLM
        if not _rag_context_is_strong(docs):
            logger.warning(
                "RAG context too weak, blocking LLM call",
                doc_count=len(docs),
                top_score=top_score,
            )
            elapsed = time.perf_counter() - t_node
            logger.info(f"[TIMING] rag_agent_node total (guardrail blocked) in {elapsed:.3f}s")
            return {
                "response": _SAFE_NO_DATA,
                "source": "guardrail",
                "metadata": {
                    **state.get("metadata", {}),
                    "retrieved_documents": len(docs),
                    "query_mode": "blocked_weak_context",
                    "guardrail": "rag_quality_check_failed",
                    "rag_retrieval_time_ms": round(t_retrieval * 1000, 1),
                },
            }

        # 4. Strong context — proceed with LLM generation
        retrieved_context = "\n\n".join(
            f"[Document {idx + 1}]\n{doc['text']}"
            for idx, doc in enumerate(docs)
        )
        system_prompt = _build_rag_system_prompt(
            query=state["query"],
            docs=docs,
            context=state.get("context"),
        )
        user_prompt = (
            f"Question: {state['query']}\n\n"
            f"Document context:\n{retrieved_context}"
        )
        t0 = time.perf_counter()
        llm_response = _llm_generate(system_prompt, user_prompt)
        t_llm = time.perf_counter() - t0

        elapsed = time.perf_counter() - t_node
        logger.info(
            f"[TIMING] rag_agent_node total in {elapsed:.3f}s "
            f"(structured={t_structured:.3f}s, retrieval={t_retrieval:.3f}s, llm={t_llm:.3f}s)"
        )
        return {"response": llm_response,
                "source": "rag",
                "metadata": {
                    **state.get("metadata", {}),
                    "retrieved_documents": len(docs),
                    "retrieved_sources": [
                        (doc.get("metadata", {}) or {}).get("source_file", "unknown")
                        for doc in docs
                    ],
                    "query_mode": "semantic_rag",
                    "rag_retrieval_time_ms": round(t_retrieval * 1000, 1),
                    "rag_llm_time_ms": round(t_llm * 1000, 1),
                }}

    # ── Aggregation agent — deterministic only, NO LLM ──────────────
    def _aggregation_agent_node(self, state: AgentState) -> dict:
        t_node = time.perf_counter()
        # Always use structured computation, never route to RAG or LLM
        t0 = time.perf_counter()
        result = _banking_query_service.answer_query(state["query"], state.get("context"))
        t_structured = time.perf_counter() - t0
        logger.info(f"[TIMING] aggregation_agent structured query in {t_structured:.3f}s (success={result.get('success')})")

        if result.get("success"):
            return {
                "response": format_structured_response(result),
                "source": "banking_data",
                "metadata": {
                    **state.get("metadata", {}),
                    "structured_result": result,
                    "query_mode": "grounded_structured",
                    "structured_query_time_ms": round(t_structured * 1000, 1),
                },
            }

        # Structured path failed — try direct pandas aggregation (no LLM)
        import os, glob, pandas as pd
        from app.services.aggregation_service import AggregationService
        agg = AggregationService()
        raw = os.path.join(settings.upload_dir, "raw")
        files = (glob.glob(os.path.join(raw, "*.csv"))
                 + glob.glob(os.path.join(raw, "*.xlsx")))
        if not files:
            files = glob.glob("data/*.csv") + glob.glob("data/*.xlsx")
        if not files:
            return {"response": _SAFE_NO_DATA,
                    "source": "aggregation",
                    "metadata": {"query_type": "aggregation", "guardrail": "no_data_files"}}
        dfs = []
        for fp in files:
            try:
                dfs.append(pd.read_csv(fp) if fp.endswith(".csv")
                           else pd.read_excel(fp))
            except Exception:
                continue
        if not dfs:
            return {"response": _SAFE_NO_DATA,
                    "source": "aggregation",
                    "metadata": {"query_type": "aggregation", "guardrail": "unreadable_files"}}
        combined = pd.concat(dfs, ignore_index=True)
        try:
            r = agg.query(combined, state["query"])
            txt = r.get("result_df", str(r.get("result", "")))
        except Exception as e:
            txt = f"Aggregation error: {e}"

        # Return deterministic result directly — no LLM summarization
        elapsed = time.perf_counter() - t_node
        logger.info(f"[TIMING] aggregation_agent_node total in {elapsed:.3f}s (pandas fallback)")
        return {"response": txt,
                "source": "aggregation",
                "metadata": {
                    **state.get("metadata", {}),
                    "query_type": "aggregation",
                    "raw_result": txt,
                    "query_mode": "deterministic_aggregation",
                }}

    def _banking_data_agent_node(self, state: AgentState) -> dict:
        t0 = time.perf_counter()
        result = _banking_query_service.answer_query(state["query"], state.get("context"))
        elapsed = time.perf_counter() - t0
        logger.info(f"[TIMING] banking_data_agent structured query in {elapsed:.3f}s (success={result.get('success')})")
        return {
            "response": format_structured_response(result),
            "source": "banking_data",
            "metadata": {
                **state.get("metadata", {}),
                "structured_result": result,
                "query_mode": "grounded_structured",
                "structured_query_time_ms": round(elapsed * 1000, 1),
            },
        }

    # ── Response formatter with LLM humanization + final safety ──────
    def _response_formatter_node(self, state: AgentState) -> dict:
        t0 = time.perf_counter()
        metadata = {
            **state.get("metadata", {}),
            "source": state.get("source", "unknown"),
            "agent_type": state.get("agent_type", "unknown"),
        }
        response = state.get("response", "")
        source = state.get("source", "unknown")
        query = state.get("query", "")

        # ── Final safety layer ───────────────────────────────────────
        # If no source, no response, or structured result had no rows → safe msg
        structured_result = metadata.get("structured_result")
        if structured_result and not structured_result.get("success"):
            response = _SAFE_NO_DATA
            metadata["guardrail"] = "structured_failure_override"
        elif not response or not response.strip():
            response = _SAFE_NO_DATA
            metadata["guardrail"] = "empty_response_override"

        # ── LLM formatting for structured responses ──────────────────
        # Only format grounded structured results into human-readable text.
        # LLM is NOT allowed to compute or infer — only rephrase.
        if (
            source in ("banking_data", "aggregation")
            and structured_result
            and structured_result.get("success")
        ):
            try:
                humanized = _llm_format_structured(query, response)
                if humanized and humanized.strip():
                    # Keep raw structured data in metadata for auditability
                    metadata["raw_structured_response"] = response
                    response = humanized
                    metadata["llm_formatted"] = True
            except Exception as e:
                logger.warning("LLM formatting failed, returning raw structured response",
                               error=str(e))
                metadata["llm_formatted"] = False

        elapsed = time.perf_counter() - t0
        logger.info(f"[TIMING] response_formatter completed in {elapsed:.3f}s (llm_formatted={metadata.get('llm_formatted', 'n/a')})")
        return {"response": response, "metadata": metadata}


# Global instance — lightweight, graph NOT compiled yet
orchestrator = OrchestratorAgent()
