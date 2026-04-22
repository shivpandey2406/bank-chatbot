# Banking Chatbot

A multi-agent banking assistant built with FastAPI, LangGraph, RAG over structured banking data, and a Streamlit frontend.

## Overview

This project combines:

- Multi-agent routing for banking workflows
- Structured data understanding across CSV and XML uploads
- Grounded RAG for document-backed responses
- Analytical and reasoning workflows for banking datasets
- A Streamlit UI for chat, uploads, agent visibility, and system stats

The chatbot is designed to answer banking questions more like an analyst than a generic chatbot. It supports:

- Informational questions
- Analytical questions such as totals, counts, top transactions, and grouped results
- Reasoning questions such as balance-change explanations
- Operational questions using maintenance and processing datasets
- Action-oriented flows such as notification and scheduling requests

## Key Capabilities

- Multi-agent orchestration using LangGraph
- FastAPI backend with documented REST APIs
- Streamlit frontend
- CSV, XLSX, XLS, and XML ingestion
- ChromaDB vector store for retrieval
- Structured banking query engine for grounded analytics
- OAuth scaffolding for Google and Slack
- Health, readiness, and service-status endpoints

## Tech Stack

- FastAPI
- LangGraph
- ChromaDB
- DuckDB
- Pydantic Settings
- Streamlit
- Pandas
- Requests
- Docker / Docker Compose

## Project Structure

```text
Banking Chatbot/
├── app/
│   ├── agents/
│   ├── api/
│   ├── core/
│   ├── db/
│   ├── models/
│   ├── rag/
│   ├── services/
│   ├── utils/
│   └── main.py
├── frontend/
│   ├── app.py
│   ├── Dockerfile
│   └── requirements.txt
├── data/
├── vectorstore/
├── docker-compose.yml
├── requirements.txt
├── .env.example
└── README.md
```

## Setup

### Prerequisites

- Python 3.11+
- pip
- Docker and Docker Compose (optional)

### 1. Clone the Project

```bash
git clone <repository-url>
cd "Banking Chatbot"
```

### 2. Create Environment File

Copy the example file and fill in your own values:

```bash
cp .env.example .env
```

Windows PowerShell:

```powershell
Copy-Item .env.example .env
```

### 3. Install Dependencies

Backend:

```bash
pip install -r requirements.txt
```

Frontend:

```bash
cd frontend
pip install -r requirements.txt
cd ..
```

### 4. Run the Backend

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 5. Run the Frontend

In a second terminal:

```bash
streamlit run frontend/app.py
```

If `streamlit` is not available on PATH:

```bash
python -m streamlit run frontend/app.py
```

### 6. Open the App

- Frontend UI: `http://localhost:8501`
- Backend API: `http://localhost:8000`
- Swagger Docs: `http://localhost:8000/docs`

## Docker Setup

Run the full stack with Docker Compose:

```bash
docker-compose up --build
```

Services:

- Frontend: `http://localhost:8501`
- Backend: `http://localhost:8000`
- Swagger Docs: `http://localhost:8000/docs`

## Environment Variables

Use `.env.example` as the template. The application supports these major groups:

- Application settings
- Server settings
- Database and vector store settings
- LLM settings
- RAG settings
- Upload settings
- Security settings
- Redis settings
- Email settings
- OAuth settings
- MCP settings
- Agent settings

Important variables:

- `OPENAI_API_KEY`
- `OPENAI_MODEL`
- `GROQ_API_KEY`
- `GROQ_MODEL`
- `DATABASE_URL`
- `VECTOR_DB_PATH`
- `UPLOAD_DIR`
- `SECRET_KEY`
- `GOOGLE_CLIENT_ID`
- `GOOGLE_CLIENT_SECRET`
- `SLACK_CLIENT_ID`
- `SLACK_CLIENT_SECRET`
- `SLACK_BOT_TOKEN`

## API Endpoints

### Health

- `GET /health`
- `GET /health/`
- `GET /health/ready`
- `GET /health/live`
- `GET /health/services`

### Chat

- `POST /api/chat/message`
- `POST /api/chat/new`
- `GET /api/chat/conversation/{conversation_id}`
- `DELETE /api/chat/conversation/{conversation_id}`
- `GET /api/chat/conversations`
- `POST /api/chat/clear`
- `GET /api/chat/agents`

### Files

- `POST /api/files/upload`
- `GET /api/files`
- `GET /api/files/{file_id}`
- `DELETE /api/files/{file_id}`
- `GET /api/files/{file_id}/preview`

### OAuth

- `GET /api/oauth/google/login`
- `GET /api/oauth/google/callback`
- `GET /api/oauth/slack/login`
- `GET /api/oauth/slack/callback`
- `GET /api/oauth/status`

## Supported Data Sources

The chatbot is designed to work with structured banking datasets such as:

- Customers
- Transactions
- Bank maintenance
- Transaction processing

Supported upload formats:

- CSV
- XLSX
- XLS
- XML

## Example Queries

- `What is the current balance for customer C0001?`
- `Give me the list of top 10 transactions`
- `Total debit last month`
- `Why did the balance change after transaction TRX010?`
- `What is the current maintenance status?`
- `List transactions for account ACC001`

## Frontend Notes

The Streamlit UI supports:

- Chat conversations
- File uploads
- Agent overview
- Health and service stats

Structured chatbot responses are rendered in a readable format in the UI, including:

- numeric results
- summaries
- explanations
- tables for list data
- source references

## Notes for Reviewers

- The backend uses grounded structured reasoning for banking analytics where possible.
- The system falls back to semantic retrieval when a direct structured answer is not available.
- Swagger documentation is available out of the box at `/docs`.

## License

This project is provided for evaluation and demonstration purposes unless otherwise specified.
