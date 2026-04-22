# 🏦 Banking Chatbot

An intelligent banking chatbot built with FastAPI, LangGraph multi-agent system, RAG pipeline, and Streamlit frontend.

## Features

### Core Capabilities
- **Multi-Agent System**: Specialized agents for different banking domains
  - Account Agent: Handle account inquiries, balances, transactions
  - Loan Agent: Loan applications, payments, interest rates
  - Compliance Agent: KYC, AML, fraud detection, regulations
  - Notification Agent: Email, SMS, Slack, push notifications
  - Scheduling Agent: Appointment booking and management

- **RAG Pipeline**: Retrieval-Augmented Generation for document-based Q&A
  - Document ingestion (CSV, Excel)
  - Semantic chunking strategies
  - Vector search with ChromaDB
  - Sentence Transformers embeddings

- **Data Aggregation**: Natural language queries on uploaded data
  - SQL-like queries through DuckDB
  - Aggregation operations (sum, avg, count, etc.)
  - Group by and filtering capabilities

- **File Management**: Upload and process banking data files
  - CSV and Excel file support
  - Automatic data validation
  - Preview and metadata extraction

## Tech Stack

### Backend
- **FastAPI**: Modern Python web framework
- **LangGraph**: Multi-agent orchestration
- **ChromaDB**: Vector database for RAG
- **Sentence Transformers**: Text embeddings
- **DuckDB**: In-memory analytics database
- **PostgreSQL**: Primary database
- **Redis**: Caching and session management

### Frontend
- **Streamlit**: Interactive web UI
- **Requests**: API communication

### Infrastructure
- **Docker & Docker Compose**: Containerization
- **PostgreSQL**: Persistent storage
- **Redis**: In-memory caching

## Project Structure

```
Banking Chatbot/
├── backend/
│   ├── app/
│   │   ├── agents/           # Multi-agent system
│   │   │   ├── orchestrator.py
│   │   │   ├── account_agent.py
│   │   │   ├── loan_agent.py
│   │   │   ├── compliance_agent.py
│   │   │   ├── notification_agent.py
│   │   │   └── scheduling_agent.py
│   │   ├── api/              # REST API endpoints
│   │   │   ├── chat.py
│   │   │   ├── files.py
│   │   │   └── health.py
│   │   ├── core/             # Core configuration
│   │   │   ├── config.py
│   │   │   ├── security.py
│   │   │   └── logging.py
│   │   ├── db/               # Database setup
│   │   │   ├── session.py
│   │   │   └── base.py
│   │   ├── models/           # Data models
│   │   │   ├── user.py
│   │   │   ├── token.py
│   │   │   ├── file.py
│   │   │   └── logs.py
│   │   ├── rag/              # RAG pipeline
│   │   │   ├── chunking.py
│   │   │   ├── embedding.py
│   │   │   ├── retrieval.py
│   │   │   ├── structured_query.py
│   │   │   └── ingestion.py
│   │   ├── services/         # Business logic
│   │   │   ├── rag_service.py
│   │   │   ├── aggregation_service.py
│   │   │   └── agent_service.py
│   │   ├── utils/            # Utilities
│   │   │   ├── file_validator.py
│   │   │   ├── date_utils.py
│   │   │   └── helpers.py
│   │   └── main.py           # Application entry point
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/
│   ├── app.py                # Streamlit application
│   ├── requirements.txt
│   └── Dockerfile
├── docker-compose.yml
├── .env                      # Environment configuration
└── README.md
```

## Quick Start

### Prerequisites
- Docker & Docker Compose
- Python 3.11+ (for local development)
- OpenAI API key (optional, for enhanced LLM capabilities)

### Running with Docker

1. Clone the repository:
```bash
git clone <repository-url>
cd Banking\ Chatbot
```

2. Configure environment variables:
```bash
cp .env.example .env
# Edit .env with your settings
```

3. Start all services:
```bash
docker-compose up -d
```

4. Access the applications:
- **Frontend (Streamlit)**: http://localhost:8501
- **Backend API**: http://localhost:8000
- **API Documentation**: http://localhost:8000/docs

### Local Development

1. Install dependencies:
```bash
# Backend
cd backend
pip install -r requirements.txt

# Frontend
cd frontend
pip install -r requirements.txt
```

2. Set up environment variables:
```bash
cp .env.example .env
```

3. Run the backend:
```bash
cd backend
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

4. Run the frontend (in a separate terminal):
```bash
cd frontend
streamlit run app.py
```

## API Endpoints

### Chat
- `POST /api/chat/message` - Send a message to the chatbot
- `GET /api/chat/conversations` - List conversations
- `GET /api/chat/conversation/{id}` - Get conversation history
- `DELETE /api/chat/conversation/{id}` - Delete a conversation
- `GET /api/chat/agents` - List available agents

### Files
- `POST /api/files/upload` - Upload a file
- `GET /api/files` - List uploaded files
- `GET /api/files/{id}` - Get file details
- `DELETE /api/files/{id}` - Delete a file
- `GET /api/files/{id}/preview` - Preview file contents

### Health
- `GET /health` - Basic health check
- `GET /health/ready` - Readiness check
- `GET /health/live` - Liveness check
- `GET /health/services` - Service status

## Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `APP_NAME` | Application name | Banking Chatbot |
| `DEBUG` | Debug mode | false |
| `SECRET_KEY` | JWT secret key | (generate one) |
| `DATABASE_URL` | PostgreSQL connection | postgresql://... |
| `OPENAI_API_KEY` | OpenAI API key | (optional) |
| `LOG_LEVEL` | Logging level | INFO |

## Agent Types

### Account Agent
Handles account-related queries:
- Balance inquiries
- Transaction history
- Account information
- Statement requests

### Loan Agent
Handles loan-related queries:
- Loan applications
- Payment information
- Interest rates
- Loan status
- Mortgage options

### Compliance Agent
Handles compliance-related queries:
- KYC requirements
- AML procedures
- Fraud prevention
- Audit information
- Regulations

### Notification Agent
Handles notification operations:
- Email sending
- SMS messages
- Slack notifications
- Push notifications
- Scheduled notifications

### Scheduling Agent
Handles appointment scheduling:
- Book appointments
- Reschedule appointments
- Cancel appointments
- Check availability

## RAG Pipeline

The RAG (Retrieval-Augmented Generation) pipeline enables the chatbot to answer questions based on uploaded documents:

1. **Ingestion**: Documents are uploaded and validated
2. **Chunking**: Content is split into semantic chunks
3. **Embedding**: Chunks are converted to vector embeddings
4. **Storage**: Embeddings are stored in ChromaDB
5. **Retrieval**: Relevant chunks are retrieved for queries
6. **Generation**: Responses are generated using retrieved context

## Data Aggregation

The aggregation engine supports natural language queries on uploaded data:

```
User: "What is the total amount by category?"
Bot: "Here's the breakdown by category..."
```

Supported operations:
- `SUM`, `AVG`, `COUNT`, `MIN`, `MAX`
- `GROUP BY` clauses
- Date range filtering
- Complex filter conditions

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## License

MIT License - see LICENSE file for details

## Support

For issues and questions:
- GitHub Issues: [Create an issue]
- Email: support@bankingchatbot.com