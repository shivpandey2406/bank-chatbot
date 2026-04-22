"""
Health API
Health check and system status endpoints.
"""

import datetime
from typing import Dict, Any, Optional

from fastapi import APIRouter
from pydantic import BaseModel

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/health", tags=["Health"])


class HealthResponse(BaseModel):
    status: str
    version: str
    timestamp: str
    services: Optional[Dict[str, Any]] = None


@router.get("", response_model=HealthResponse)
@router.get("/", response_model=HealthResponse)
async def health_check():
    return HealthResponse(
        status="healthy",
        version=settings.app_version,
        timestamp=datetime.datetime.now().isoformat(),
    )


@router.get("/ready", response_model=HealthResponse)
async def readiness_check():
    try:
        services_status = await check_services()
        all_healthy = all(s.get("status") == "healthy" for s in services_status.values())
        return HealthResponse(
            status="ready" if all_healthy else "not_ready",
            version=settings.app_version,
            timestamp=datetime.datetime.now().isoformat(),
            services=services_status,
        )
    except Exception as e:
        return HealthResponse(
            status="not_ready",
            version=settings.app_version,
            timestamp=datetime.datetime.now().isoformat(),
            services={"error": str(e)},
        )


@router.get("/live", response_model=HealthResponse)
async def liveness_check():
    return HealthResponse(
        status="alive",
        version=settings.app_version,
        timestamp=datetime.datetime.now().isoformat(),
    )


async def check_services() -> Dict[str, Any]:
    services: Dict[str, Any] = {}

    # Vector store
    try:
        from app.rag.retrieval import get_vector_store
        vs = get_vector_store()
        info = vs.get_collection_info()
        services["vector_store"] = {"status": "healthy", "message": "OK", "info": info}
    except Exception as e:
        services["vector_store"] = {"status": "unhealthy", "message": str(e)}

    # Embedding model
    try:
        from app.rag.embedding import get_global_embedding_model
        em = get_global_embedding_model()
        dim = em.dimension
        services["embedding_model"] = {"status": "healthy", "message": f"dim={dim}"}
    except Exception as e:
        services["embedding_model"] = {"status": "unhealthy", "message": str(e)}

    # Agent system
    try:
        from app.services.agent_service import AgentService
        agent_svc = AgentService()
        st = await agent_svc.get_system_status()
        services["agent_system"] = {
            "status": "healthy" if st.get("success") else "unhealthy",
            "message": "operational",
            "agents_available": st.get("system_status", {}).get("agents_available", 0),
        }
    except Exception as e:
        services["agent_system"] = {"status": "unhealthy", "message": str(e)}

    return services


@router.get("/services")
async def services_status():
    return await check_services()
