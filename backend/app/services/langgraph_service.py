
# Simplified LangGraph-like flow
class AgentRouter:
    def route(self, query):
        if "sum" in query:
            return "aggregation"
        elif "email" in query:
            return "gmail"
        return "rag"
