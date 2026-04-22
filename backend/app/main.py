
from fastapi import FastAPI
from app.routers import upload, query, integrations

app = FastAPI(title="Production RAG System")

app.include_router(upload.router)
app.include_router(query.router)
app.include_router(integrations.router)

@app.get("/")
def root():
    return {"status": "running"}
