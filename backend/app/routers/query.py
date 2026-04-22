
from fastapi import APIRouter
from app.services.rag_service import RAGService
from app.services.aggregation_service import AggregationService
from app.services.langgraph_service import AgentRouter

router = APIRouter(prefix="/query")

rag = RAGService()
agg = AggregationService()
router_agent = AgentRouter()

@router.post("/")
def query(q: str):
    route = router_agent.route(q)

    if route == "aggregation":
        return {"result": "Aggregation logic triggered"}
    elif route == "rag":
        return rag.query(q)
    else:
        return {"message": "Integration route"}
