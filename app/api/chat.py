"""
Chat API
Main chat endpoint for the banking chatbot.
"""

import os
import uuid
import glob
from datetime import datetime
from typing import Dict, Any, Optional, List

from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from app.core.config import settings
from app.core.logging import get_logger
from app.core.security import get_current_user

logger = get_logger(__name__)

router = APIRouter(prefix="/api/chat", tags=["Chat"])


# ── Request / Response models ────────────────────────────────────────

class ChatRequest(BaseModel):
    message: str = Field(..., description="Your message")


class ChatResponse(BaseModel):
    success: bool
    response: str
    conversation_id: str
    source: Optional[str] = None
    agent_type: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    timestamp: str


# ── In-memory conversation store ─────────────────────────────────────

conversations: Dict[str, List[Dict[str, Any]]] = {}
# Track which conversation_id belongs to which "session"
# For simplicity: one global active conversation per server restart
_active_conv_id: Optional[str] = None


def _gen_conv_id() -> str:
    return str(uuid.uuid4())


def _get_or_create_conv() -> str:
    """Return the active conversation, or create a new one."""
    global _active_conv_id
    if _active_conv_id is None:
        _active_conv_id = _gen_conv_id()
    return _active_conv_id


def _store_msg(conv_id: str, role: str, content: str,
               metadata: Optional[Dict[str, Any]] = None):
    conversations.setdefault(conv_id, []).append({
        "role": role,
        "content": content,
        "metadata": metadata or {},
        "timestamp": datetime.now().isoformat(),
    })


def _build_context(conv_id: str) -> Dict[str, Any]:
    ctx: Dict[str, Any] = {}
    if conv_id in conversations:
        ctx["recent_messages"] = conversations[conv_id][-6:]
    return ctx


def _detect_metadata() -> Dict[str, Any]:
    """Auto-detect metadata from uploaded files."""
    meta: Dict[str, Any] = {"uploaded_files": []}
    raw_dir = os.path.join(settings.upload_dir, "raw")
    files = glob.glob(os.path.join(raw_dir, "*.csv")) + \
            glob.glob(os.path.join(raw_dir, "*.xlsx")) + \
            glob.glob(os.path.join(raw_dir, "*.xls")) + \
            glob.glob(os.path.join(raw_dir, "*.xml"))
    if not files:
        files = (
            glob.glob("data/*.csv")
            + glob.glob("data/*.xlsx")
            + glob.glob("data/*.xls")
            + glob.glob("data/*.xml")
        )
    for fp in files:
        meta["uploaded_files"].append(os.path.basename(fp))
    meta["file_count"] = len(meta["uploaded_files"])
    return meta


# ── Main chat endpoint ───────────────────────────────────────────────

@router.post("/message", response_model=ChatResponse)
async def chat_message(
    request: ChatRequest,
    background_tasks: BackgroundTasks,
    current_user: Optional[dict] = Depends(get_current_user),
):
    """
    Send a message. Just provide `{"message": "your question"}`.
    Conversation and metadata are handled automatically.
    """
    logger.info(f"Chat message: {request.message[:100]}...")

    try:
        from app.services.agent_service import AgentService
        agent_service = AgentService()

        conv_id = _get_or_create_conv()
        context = _build_context(conv_id)
        context["metadata"] = _detect_metadata()

        if current_user:
            context["user"] = {
                "user_id": current_user.get("sub", "anonymous"),
                "is_authenticated": True,
            }

        result = await agent_service.process_query(
            query=request.message, context=context
        )

        _store_msg(conv_id, "user", request.message)
        _store_msg(conv_id, "assistant",
                   result.get("response", ""),
                   result.get("metadata", {}))

        return ChatResponse(
            success=result.get("success", False),
            response=result.get("response", ""),
            conversation_id=conv_id,
            source=result.get("source", "unknown"),
            agent_type=result.get("agent_type", "unknown"),
            metadata=result.get("metadata", {}),
            timestamp=datetime.now().isoformat(),
        )
    except Exception as e:
        logger.exception("Error processing chat message", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


# ── Conversation management ──────────────────────────────────────────

@router.post("/new")
async def new_conversation():
    """Start a fresh conversation."""
    global _active_conv_id
    _active_conv_id = _gen_conv_id()
    return {"success": True, "conversation_id": _active_conv_id}


@router.get("/conversation/{conversation_id}")
async def get_conversation(conversation_id: str):
    if conversation_id not in conversations:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return conversations[conversation_id]


@router.delete("/conversation/{conversation_id}")
async def delete_conversation(conversation_id: str):
    global _active_conv_id
    if conversation_id not in conversations:
        raise HTTPException(status_code=404, detail="Conversation not found")
    del conversations[conversation_id]
    if _active_conv_id == conversation_id:
        _active_conv_id = None
    return {"success": True, "message": "Conversation deleted"}


@router.get("/conversations")
async def list_conversations():
    return [
        {
            "conversation_id": cid,
            "message_count": len(msgs),
            "last_message": msgs[-1]["content"] if msgs else "",
            "last_updated": msgs[-1].get("timestamp", "") if msgs else "",
        }
        for cid, msgs in conversations.items()
    ]


@router.post("/clear")
async def clear_conversations():
    global _active_conv_id
    conversations.clear()
    _active_conv_id = None
    return {"success": True, "message": "All conversations cleared"}


@router.get("/agents")
async def list_agents():
    from app.services.agent_service import AgentService
    return await AgentService().get_agent_capabilities()
