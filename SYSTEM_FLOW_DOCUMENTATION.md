# Banking Chatbot - System Flow Documentation

This document provides a comprehensive step-by-step explanation of how the Banking Chatbot system works. It covers the architecture, data flow, and interaction between components.

---

## 📋 Table of Contents

1. [System Architecture Overview](#system-architecture-overview)
2. [Technology Stack](#technology-stack)
3. [Application Startup Flow](#application-startup-flow)
4. [Chat Message Flow](#chat-message-flow)
5. [Multi-Agent Orchestration Flow](#multi-agent-orchestration-flow)
6. [RAG (Retrieval-Augmented Generation) Flow](#rag-retrieval-augmented-generation-flow)
7. [File Upload and Ingestion Flow](#file-upload-and-ingestion-flow)
8. [Frontend to Backend Communication](#frontend-to-backend-communication)
9. [Data Flow Diagrams](#data-flow-diagrams)

---

## 🏗️ System Architecture Overview

The Banking Chatbot is built with a **three-tier architecture**:

```
┌─────────────────────────────────────────────────────────────────────┐
│                         FRONTEND LAYER                               │
│                    Streamlit Web Application                         │
│                      (frontend/app.py)                               │
└─────────────────────────────┬───────────────────────────────────────┘
                              │ HTTP/REST API
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│                         API LAYER                                    │
│                    FastAPI Backend Server                            │
│                      (app/main.py)                                   │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐ │
│  │  Chat API   │  │  Files API  │  │ Health API  │  │  OAuth API  │ │
│  │ (app/api/)  │  │ (app/api/)  │  │ (app/api/)  │  │ (app/api/)  │ │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘ │
└─────────┼────────────────┼────────────────┼────────────────┼────────┘
          │                │                │                │
          ▼                ▼                ▼                ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      SERVICE LAYER                                   │
│  ┌─────────────────────┐  ┌─────────────────────┐                   │
│  │    Agent Service    │  │     RAG Service     │                   │
│  │  (coordinates       │  │  (vector store      │                   │
│  │   agents)           │  │   operations)       │                   │
│  └─────────┬───────────┘  └─────────┬───────────┘                   │
│            │                        │                                 │
│  ┌─────────▼────────────────────────▼───────────┐                   │
│  │              ORCHESTRATOR                     │                   │
│  │         (LangGraph Workflow)                  │                   │
│  │  ┌─────────┐ ┌─────────┐ ┌─────────┐         │                   │
│  │  │ Router  │→│ Specialized Agents │→│Formatter│                   │
│  │  └─────────┘ └─────────┘ └─────────┘         │                   │
│  └───────────────────────────────────────────────┘                   │
└─────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      DATA LAYER                                      │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐                  │
│  │  ChromaDB   │  │  SQLite/    │  │   File      │                  │
│  │ (Vector DB) │  │  Database   │  │   Storage   │                  │
│  └─────────────┘  └─────────────┘  └─────────────┘                  │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 💻 Technology Stack

| Component | Technology | Purpose |
|-----------|------------|---------|
| **Frontend** | Streamlit | Web UI for chat, uploads, and monitoring |
| **Backend Framework** | FastAPI | REST API server |
| **Agent Orchestration** | LangGraph | Multi-agent workflow management |
| **Vector Database** | ChromaDB | Document storage and semantic search |
| **Embeddings** | SentenceTransformers / OpenAI | Text vectorization |
| **LLM** | OpenAI / Groq | Response generation |
| **Data Processing** | Pandas, DuckDB | CSV/Excel/XML processing |
| **Database** | SQLite | User data, conversations, logs |

---

## 🚀 Application Startup Flow

### Step-by-Step Startup Process:

```
1. Server Start (uvicorn app.main:app)
   │
   ▼
2. FastAPI App Creation (create_app())
   │
   ├── Setup Logging (app/core/logging.py)
   ├── Load Configuration (.env → Settings)
   └── Register Middleware (CORS, GZip)
   │
   ▼
3. Lifespan Event: Startup
   │
   ├── Initialize Database (init_db)
   │   └── Create SQLite tables for users, files, logs
   │
   ├── Create Default User (create_default_user)
   │   └── Admin user for authentication
   │
   └── Log: "Embedding model and vector store will load on first use"
       └── Lazy loading for fast startup
   │
   ▼
4. Register API Routes
   │
   ├── /health (Health checks)
   ├── /api/chat (Chat endpoints)
   ├── /api/files (File upload/management)
   ├── /api/oauth (OAuth connections)
   └── /api/mcp (MCP tool integrations)
   │
   ▼
5. Server Ready
   └── Listening on http://localhost:8000
```

### Key Files Involved:
- `app/main.py` - Entry point and app configuration
- `app/core/config.py` - Settings management
- `app/db/session.py` - Database initialization

---

## 💬 Chat Message Flow

### Complete Request-Response Cycle:

```
┌──────────────────────────────────────────────────────────────────────┐
│ STEP 1: USER SENDS MESSAGE                                           │
├──────────────────────────────────────────────────────────────────────┤
│ Frontend (Streamlit):                                                │
│   1. User types message in chat input                                │
│   2. Clicks "Send" or presses Enter                                  │
│   3. handle_user_message() is called                                 │
│   4. Message added to st.session_state.messages                      │
│   5. API call: POST /api/chat/message                                │
│      Body: {"message": "What is my account balance?"}                │
└──────────────────────────────────────────────────────────────────────┘
                                   │
                                   ▼
┌──────────────────────────────────────────────────────────────────────┐
│ STEP 2: BACKEND RECEIVES REQUEST                                     │
├──────────────────────────────────────────────────────────────────────┤
│ Chat API (app/api/chat.py):                                          │
│   1. Endpoint: @router.post("/message")                              │
│   2. Validates request                                               │
│   3. Gets or creates conversation ID                                 │
│   4. Builds context with:                                            │
│      - Recent messages (last 6)                                      │
│      - Uploaded files metadata                                       │
│      - User authentication info                                      │
│   5. Calls AgentService.process_query()                              │
└──────────────────────────────────────────────────────────────────────┘
                                   │
                                   ▼
┌──────────────────────────────────────────────────────────────────────┐
│ STEP 3: AGENT SERVICE PROCESSING                                     │
├──────────────────────────────────────────────────────────────────────┤
│ Agent Service (app/services/agent_service.py):                       │
│   1. Receives query and context                                      │
│   2. Calls orchestrator.process_query()                              │
│   3. Returns result with response, source, agent_type                │
└──────────────────────────────────────────────────────────────────────┘
                                   │
                                   ▼
┌──────────────────────────────────────────────────────────────────────┐
│ STEP 4: STORE CONVERSATION                                           │
├──────────────────────────────────────────────────────────────────────┤
│ Chat API:                                                            │
│   1. Stores user message in conversation history                     │
│   2. Stores assistant response with metadata                         │
│   3. Prepares ChatResponse with:                                     │
│      - success: bool                                                 │
│      - response: str                                                 │
│      - conversation_id: str                                          │
│      - source: str (which agent answered)                            │
│      - agent_type: str                                               │
│      - metadata: dict                                                │
│      - timestamp: str                                                │
└──────────────────────────────────────────────────────────────────────┘
                                   │
                                   ▼
┌──────────────────────────────────────────────────────────────────────┐
│ STEP 5: FRONTEND DISPLAYS RESPONSE                                   │
├──────────────────────────────────────────────────────────────────────┤
│ Frontend (Streamlit):                                                │
│   1. Receives JSON response                                          │
│   2. Adds assistant message to session_state.messages                │
│   3. Checks if response has structured data (metadata.structured_result)│
│   4. If structured: render_structured_response()                     │
│      - Displays summary, results, tables, sources                    │
│   5. If plain text: st.markdown()                                    │
│   6. Shows metadata in expandable "📋 Details" section               │
└──────────────────────────────────────────────────────────────────────┘
```

### Key Files Involved:
- `app/api/chat.py` - Chat endpoint
- `app/services/agent_service.py` - Agent coordination
- `frontend/app.py` - UI handling

---

## 🤖 Multi-Agent Orchestration Flow

### LangGraph-Based Agent Routing:

```
┌──────────────────────────────────────────────────────────────────────┐
│ ORCHESTRATOR WORKFLOW (app/agents/orchestrator.py)                   │
├──────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  ┌─────────────────────────────────────────────────────────────────┐ │
│  │                    ENTRY: Router Node                           │ │
│  │                                                                 │ │
│  │  1. Receives query: "What is my account balance?"               │ │
│  │  2. Calls BankingQueryService.classify_intent()                 │ │
│  │  3. Falls back to keyword-based _classify_query()               │ │
│  │  4. Determines agent_type based on:                             │ │
│  │     - Intent classification                                     │ │
│  │     - Keyword matching                                          │ │
│  │  5. Sets state["agent_type"]                                    │ │
│  └─────────────────────────────────────────────────────────────────┘ │
│                              │                                       │
│                              ▼                                       │
│  ┌─────────────────────────────────────────────────────────────────┐ │
│  │                   ROUTING DECISION                              │ │
│  │                                                                 │ │
│  │  _route_query() returns one of:                                 │ │
│  │                                                                 │ │
│  │  ┌──────────────────┐  ┌──────────────────┐                     │ │
│  │  │ account_agent    │  │ loan_agent       │                     │ │
│  │  │ (account balance,│  │ (loans, credit,  │                     │ │
│  │  │  transactions)   │  │  interest rates) │                     │ │
│  │  └──────────────────┘  └──────────────────┘                     │ │
│  │                                                                 │ │
│  │  ┌──────────────────┐  ┌──────────────────┐                     │ │
│  │  │ compliance_agent │  │ notification_    │                     │ │
│  │  │ (KYC, AML,       │  │ agent            │                     │ │
│  │  │  regulations)    │  │ (alerts, emails, │                     │ │
│  │  └──────────────────┘  │  SMS)            │                     │ │
│  │                        └──────────────────┘                     │ │
│  │                                                                 │ │
│  │  ┌──────────────────┐  ┌──────────────────┐                     │ │
│  │  │ scheduling_      │  │ rag_agent        │                     │ │
│  │  │ agent            │  │ (document-based  │                     │ │
│  │  │ (appointments,   │  │  Q&A)            │                     │ │
│  │  │  meetings)       │  └──────────────────┘                     │ │
│  │  └──────────────────┘                                           │ │
│  │                                                                 │ │
│  │  ┌──────────────────┐  ┌──────────────────┐                     │ │
│  │  │ aggregation_     │  │ banking_data_    │                     │ │
│  │  │ agent            │  │ agent            │                     │ │
│  │  │ (sum, total,     │  │ (general banking │                     │ │
│  │  │  average)        │  │  queries)        │                     │ │
│  │  └──────────────────┘  └──────────────────┘                     │ │
│  └─────────────────────────────────────────────────────────────────┘ │
│                              │                                       │
│                              ▼                                       │
│  ┌─────────────────────────────────────────────────────────────────┐ │
│  │               SPECIALIZED AGENT PROCESSING                      │ │
│  │                                                                 │ │
│  │  Each agent processes the query and returns:                    │ │
│  │  - response: The answer text                                    │ │
│  │  - source: Agent identifier                                     │ │
│  │  - metadata: Additional context                                 │ │
│  └─────────────────────────────────────────────────────────────────┘ │
│                              │                                       │
│                              ▼                                       │
│  ┌─────────────────────────────────────────────────────────────────┐ │
│  │               RESPONSE FORMATTER NODE                           │ │
│  │                                                                 │ │
│  │  1. Collects response from specialized agent                    │ │
│  │  2. Adds metadata (source, agent_type)                          │ │
│  │  3. Returns final state                                         │ │
│  └─────────────────────────────────────────────────────────────────┘ │
│                              │                                       │
│                              ▼                                       │
│  ┌─────────────────────────────────────────────────────────────────┐ │
│  │                    EXIT (END)                                   │ │
│  │                                                                 │ │
│  │  Returns: {                                                     │ │
│  │    "success": true,                                             │ │
│  │    "response": "...",                                           │ │
│  │    "source": "banking_data",                                    │ │
│  │    "agent_type": "banking_data_agent",                          │ │
│  │    "metadata": {...}                                            │ │
│  │  }                                                              │ │
│  └─────────────────────────────────────────────────────────────────┘ │
│                                                                      │
└──────────────────────────────────────────────────────────────────────┘
```

### Agent Classification Keywords:

| Agent | Keywords |
|-------|----------|
| **account_agent** | account balance, account number, check balance, my account, account statement, transaction history |
| **loan_agent** | loan, mortgage, credit, interest rate, loan application, APR, loan term, refinance |
| **compliance_agent** | compliance, regulation, policy, audit, KYC, AML, fraud, suspicious, report, violation |
| **notification_agent** | notify, alert, send message, email, SMS, notification, remind |
| **scheduling_agent** | schedule, appointment, meeting, calendar, remind me, set up, book, reserve |
| **aggregation_agent** | sum of, total of, total revenue, average, group by, aggregate, statistics, how much, how many |
| **banking_data_agent** | Default fallback for all other queries |

### Key Files Involved:
- `app/agents/orchestrator.py` - Main orchestrator with LangGraph
- `app/agents/account_agent.py` - Account queries
- `app/agents/loan_agent.py` - Loan queries
- `app/agents/compliance_agent.py` - Compliance queries
- `app/agents/notification_agent.py` - Notifications
- `app/agents/scheduling_agent.py` - Scheduling

---

## 🔍 RAG (Retrieval-Augmented Generation) Flow

### Document Retrieval and Response Generation:

```
┌──────────────────────────────────────────────────────────────────────┐
│ STEP 1: QUERY ARRIVES AT RAG AGENT                                   │
├──────────────────────────────────────────────────────────────────────┤
│ Orchestrator routes to rag_agent when:                               │
│   - Query is document-specific                                       │
│   - Other agents don't have structured answers                       │
│   - Fallback from banking_data_agent                                 │
└──────────────────────────────────────────────────────────────────────┘
                                   │
                                   ▼
┌──────────────────────────────────────────────────────────────────────┐
│ STEP 2: VECTOR STORE SEARCH                                          │
├──────────────────────────────────────────────────────────────────────┤
│ RAGService.retrieve():                                               │
│   1. Query: "What are the withdrawal policies?"                      │
│   2. Generate query embedding                                        │
│      - Uses SentenceTransformer or OpenAI embeddings                 │
│      - Converts text to vector (e.g., 384 or 1536 dimensions)        │
│   3. Search ChromaDB                                                 │
│      - Cosine similarity search                                      │
│      - Returns top-k documents (default: 4)                          │
│      - Each result includes: text, metadata, score                   │
└──────────────────────────────────────────────────────────────────────┘
                                   │
                                   ▼
┌──────────────────────────────────────────────────────────────────────┐
│ STEP 3: BUILD PROMPT WITH CONTEXT                                    │
├──────────────────────────────────────────────────────────────────────┤
│ _build_rag_system_prompt():                                          │
│   1. System prompt includes:                                         │
│      - Persona: "Nova, a helpful banking operations chatbot"         │
│      - Instructions: Use documents first, be direct and warm         │
│      - Style: Professional banking assistant                         │
│   2. Context includes:                                               │
│      - User question                                                 │
│      - Uploaded files list                                           │
│      - Recent conversation (last 4 messages)                         │
│      - Retrieved document matches with scores                        │
│   3. Answer style instructions:                                      │
│      - Start with the answer                                         │
│      - Cite document names naturally                                 │
│      - Don't mention system internals                                │
└──────────────────────────────────────────────────────────────────────┘
                                   │
                                   ▼
┌──────────────────────────────────────────────────────────────────────┐
│ STEP 4: LLM GENERATION                                               │
├──────────────────────────────────────────────────────────────────────┤
│ _llm_generate():                                                     │
│   1. Call OpenAI-compatible API                                      │
│      - Model: configured in .env (gpt-4, gpt-3.5-turbo, etc.)        │
│      - Temperature: controls randomness                              │
│      - Max tokens: response length limit                             │
│   2. Messages:                                                       │
│      - System: Built prompt with persona and context                 │
│      - User: Question + retrieved documents                          │
│   3. Returns generated response                                      │
└──────────────────────────────────────────────────────────────────────┘
                                   │
                                   ▼
┌──────────────────────────────────────────────────────────────────────┐
│ STEP 5: RETURN RAG RESPONSE                                          │
├──────────────────────────────────────────────────────────────────────┤
│ Returns: {                                                           │
│   "response": "Based on the uploaded policy document...",            │
│   "source": "rag",                                                   │
│   "metadata": {                                                      │
│     "retrieved_documents": 4,                                        │
│     "retrieved_sources": ["policy_doc.pdf", "faq.txt"],              │
│     "query_mode": "semantic_rag"                                     │
│   }                                                                  │
│ }                                                                    │
└──────────────────────────────────────────────────────────────────────┘
```

### Embedding Process:

```
┌──────────────────────────────────────────────────────────────────────┐
│ EMBEDDING GENERATION (app/rag/embedding.py)                          │
├──────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  Text Input: "What are the withdrawal policies?"                     │
│                              │                                       │
│                              ▼                                       │
│  ┌─────────────────────────────────────────────────────────────────┐ │
│  │              EMBEDDING MODEL SELECTION                          │ │
│  │                                                                 │ │
│  │  If OpenAI configured and API key valid:                        │ │
│  │    → OpenAIEmbeddings (text-embedding-3-small, 1536 dims)       │ │
│  │  Else:                                                          │ │
│  │    → SentenceTransformerEmbeddings (all-MiniLM-L6-v2, 384 dims) │ │
│  └─────────────────────────────────────────────────────────────────┘ │
│                              │                                       │
│                              ▼                                       │
│  ┌─────────────────────────────────────────────────────────────────┐ │
│  │              VECTOR GENERATION                                  │ │
│  │                                                                 │ │
│  │  Input text → Tokenization → Model Processing → Vector Output   │ │
│  │                                                                 │ │
│  │  Example output (simplified):                                   │ │
│  │  [0.123, -0.456, 0.789, ..., -0.234]                            │ │
│  └─────────────────────────────────────────────────────────────────┘ │
│                              │                                       │
│                              ▼                                       │
│  Normalized vector (L2 normalization for cosine similarity)          │
└──────────────────────────────────────────────────────────────────────┘
```

### Key Files Involved:
- `app/services/rag_service.py` - RAG operations
- `app/rag/retrieval.py` - Vector store search
- `app/rag/embedding.py` - Embedding generation
- `app/rag/chunking.py` - Text chunking

---

## 📤 File Upload and Ingestion Flow

### Complete Upload Pipeline:

```
┌──────────────────────────────────────────────────────────────────────┐
│ STEP 1: USER UPLOADS FILE                                            │
├──────────────────────────────────────────────────────────────────────┤
│ Frontend (Streamlit):                                                │
│   1. User navigates to "📁 Upload Files" page                        │
│   2. Selects file (CSV, XLSX, XLS, or XML)                          │
│   3. Clicks "🚀 Upload and Process"                                  │
│   4. API call: POST /api/files/upload                                │
│      - Sends file as multipart/form-data                            │
└──────────────────────────────────────────────────────────────────────┘
                                   │
                                   ▼
┌──────────────────────────────────────────────────────────────────────┐
│ STEP 2: BACKEND RECEIVES FILE                                        │
├──────────────────────────────────────────────────────────────────────┤
│ Files API (app/api/files.py):                                        │
│   1. Endpoint: @router.post("/upload")                               │
│   2. Receives UploadFile                                              │
│   3. Generates unique file_id (UUID)                                 │
│   4. Creates upload directory if needed                              │
│   5. Saves file to: {upload_dir}/raw/{file_id}_{filename}            │
└──────────────────────────────────────────────────────────────────────┘
                                   │
                                   ▼
┌──────────────────────────────────────────────────────────────────────┐
│ STEP 3: FILE VALIDATION                                              │
├──────────────────────────────────────────────────────────────────────┤
│ FileValidator.validate_file():                                       │
│   1. Check file extension (.csv, .xlsx, .xls, .xml)                  │
│   2. Verify file is not empty                                        │
│   3. Parse file and extract:                                         │
│      - row_count: Number of data rows                                │
│      - column_count: Number of columns                               │
│      - columns: Column names                                         │
│      - file_type: Detected type                                      │
│      - sample_data: First few rows                                   │
│   4. Generate warnings if any issues                                 │
│   5. Return ValidationResult                                          │
└──────────────────────────────────────────────────────────────────────┘
                                   │
                                   ▼
┌──────────────────────────────────────────────────────────────────────┐
│ STEP 4: RAG INGESTION                                                │
├──────────────────────────────────────────────────────────────────────┤
│ ingest_file() (app/rag/ingestion.py):                                │
│   1. Read file based on type:                                        │
│      - CSV → pandas.read_csv()                                       │
│      - XLSX/XLS → pandas.read_excel()                                │
│      - XML → Parse with ElementTree                                  │
│   2. Process data into chunks:                                       │
│                                                                      │
│      For CSV/Excel:                                                  │
│      ├── Row-level chunks: Each row → text description               │
│      ├── Summary chunk: Dataset statistics                           │
│      └── Column chunks: Schema info for each column                  │
│                                                                      │
│      For XML:                                                        │
│      ├── Document chunk: Full XML as text                            │
│      └── Record chunks: Each XML record → text                       │
│                                                                      │
│   3. Chunking strategies:                                            │
│      - Fixed size: Split by character count                          │
│      - Semantic: Split by paragraphs/sections                        │
│   4. Each chunk gets metadata:                                       │
│      - source_file: Original filename                                │
│      - file_type: csv/xlsx/xml                                       │
│      - row_index: Which row (if row-level)                           │
│      - chunk_type: row/summary/column_schema                         │
└──────────────────────────────────────────────────────────────────────┘
                                   │
                                   ▼
┌──────────────────────────────────────────────────────────────────────┐
│ STEP 5: EMBEDDING GENERATION                                         │
├──────────────────────────────────────────────────────────────────────┤
│ EmbeddingModel.embed():                                              │
│   1. Take all chunk texts                                            │
│   2. Generate embeddings using:                                      │
│      - SentenceTransformer (local, free)                             │
│      - Or OpenAI API (if configured)                                 │
│   3. Each chunk → vector (384 or 1536 dimensions)                    │
└──────────────────────────────────────────────────────────────────────┘
                                   │
                                   ▼
┌──────────────────────────────────────────────────────────────────────┐
│ STEP 6: VECTOR STORE STORAGE                                         │
├──────────────────────────────────────────────────────────────────────┤
│ VectorStore.add_documents():                                         │
│   1. Connect to ChromaDB (persistent at vectorstore/chroma/)         │
│   2. Get or create "documents" collection                            │
│   3. Add documents with:                                             │
│      - documents: Chunk text                                         │
│      - embeddings: Generated vectors                                 │
│      - metadatas: Chunk metadata                                     │
│      - ids: Unique document IDs                                      │
│   4. ChromaDB stores in vector format for similarity search          │
└──────────────────────────────────────────────────────────────────────┘
                                   │
                                   ▼
┌──────────────────────────────────────────────────────────────────────┐
│ STEP 7: RETURN UPLOAD RESULT                                         │
├──────────────────────────────────────────────────────────────────────┤
│ FileUploadResponse:                                                  │
│   {                                                                  │
│     "success": true,                                                 │
│     "file_id": "uuid",                                               │
│     "filename": "transactions.csv",                                  │
│     "file_type": "csv",                                              │
│     "row_count": 1000,                                               │
│     "column_count": 8,                                               │
│     "chunk_count": 3005,  // rows + summary + columns                │
│     "columns": ["id", "date", "amount", ...],                        │
│     "message": "File uploaded and processed successfully"            │
│   }                                                                  │
└──────────────────────────────────────────────────────────────────────┘
                                   │
                                   ▼
┌──────────────────────────────────────────────────────────────────────┐
│ STEP 8: FRONTEND DISPLAYS RESULT                                     │
├──────────────────────────────────────────────────────────────────────┤
│ Streamlit shows:                                                     │
│   - ✅ Success message                                               │
│   - Metrics: Rows, Columns, Chunks, File Type                        │
│   - Column names list                                                │
│   - Any warnings                                                     │
│   - File added to "Uploaded Files" section                           │
└──────────────────────────────────────────────────────────────────────┘
```

### Chunking Strategy Example:

For a CSV with 100 rows and 5 columns:
- **Row chunks**: 100 chunks (one per row)
- **Summary chunk**: 1 chunk (dataset overview)
- **Column chunks**: 5 chunks (one per column schema)
- **Total**: 106 chunks

### Key Files Involved:
- `app/api/files.py` - Upload endpoint
- `app/rag/ingestion.py` - Ingestion pipeline
- `app/rag/chunking.py` - Text chunking strategies
- `app/utils/file_validator.py` - File validation

---

## 🖥️ Frontend to Backend Communication

### API Communication Flow:

```
┌──────────────────────────────────────────────────────────────────────┐
│ STREAMLIT FRONTEND (frontend/app.py)                                 │
├──────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  API Helper Function:                                                │
│  ┌────────────────────────────────────────────────────────────────┐ │
│  │ def api(endpoint, method="GET", data=None, files=None):        │ │
│  │     url = f"{API_BASE_URL}{endpoint}"                          │ │
│  │     # API_BASE_URL from environment (default: http://localhost:8000)│ │
│  │     if method == "GET":                                        │ │
│  │         r = requests.get(url, timeout=30)                      │ │
│  │     elif method == "POST":                                     │ │
│  │         if files:                                              │ │
│  │             r = requests.post(url, files=files, timeout=60)    │ │
│  │         else:                                                  │ │
│  │             r = requests.post(url, json=data, timeout=30)      │ │
│  │     elif method == "DELETE":                                   │ │
│  │         r = requests.delete(url, timeout=30)                   │ │
│  │     return r.json()                                            │ │
│  └────────────────────────────────────────────────────────────────┘ │
│                                                                      │
└──────────────────────────────────────────────────────────────────────┘
                                   │
                                   │ HTTP Requests
                                   ▼
┌──────────────────────────────────────────────────────────────────────┐
│ FASTAPI BACKEND (app/main.py)                                        │
├──────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  CORS Middleware:                                                    │
│  - Allows requests from Streamlit (default: all origins)             │
│  - Handles preflight OPTIONS requests                                │
│                                                                      │
│  GZip Middleware:                                                    │
│  - Compresses responses > 1KB                                        │
│                                                                      │
└──────────────────────────────────────────────────────────────────────┘
```

### API Endpoints Used by Frontend:

| Page | Endpoint | Method | Purpose |
|------|----------|--------|---------|
| Chat | `/api/chat/message` | POST | Send chat message |
| Chat | `/api/chat/new` | POST | Start new conversation |
| Chat | `/api/chat/agents` | GET | List available agents |
| Upload | `/api/files/upload` | POST | Upload file |
| Agents | `/api/chat/agents` | GET | Show agent capabilities |
| Agents | `/health` | GET | Check backend health |
| Agents | `/health/services` | GET | Service status |
| Integrations | `/api/oauth/status` | GET | OAuth connection status |
| Integrations | `/api/mcp/gmail/send` | POST | Send email via Gmail |
| Integrations | `/api/mcp/calendar/create` | POST | Create calendar event |
| Integrations | `/api/mcp/slack/send` | POST | Send Slack message |

---

## 📊 Data Flow Diagrams

### Complete System Data Flow:

```
┌──────────────────────────────────────────────────────────────────────────────────┐
│                              COMPLETE SYSTEM DATA FLOW                            │
└──────────────────────────────────────────────────────────────────────────────────┘

                                    ┌─────────────┐
                                    │   Browser   │
                                    │  (User UI)  │
                                    └──────┬──────┘
                                           │
                                           │ HTTP/REST
                                           ▼
┌──────────────────────────────────────────────────────────────────────────────────┐
│                              STREAMLIT FRONTEND                                   │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐             │
│  │    Chat     │  │   Upload    │  │   Agents    │  │    Stats    │             │
│  │    Page     │  │    Page     │  │    Page     │  │    Page     │             │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘             │
│         │                │                │                │                     │
│         └────────────────┴────────────────┴────────────────┘                     │
│                                  │                                               │
│                           requests library                                       │
│                                  │                                               │
└──────────────────────────────────┼────────────────────────────────────────────────┘
                                   │
                                   │ POST /api/chat/message
                                   │ POST /api/files/upload
                                   │ GET /api/chat/agents
                                   │ GET /health
                                   ▼
┌──────────────────────────────────────────────────────────────────────────────────┐
│                              FASTAPI BACKEND                                      │
│  ┌─────────────────────────────────────────────────────────────────────────────┐ │
│  │                           API ROUTERS                                        │ │
│  │  ┌───────────┐  ┌───────────┐  ┌───────────┐  ┌───────────┐                │ │
│  │  │ Chat API  │  │ Files API │  │Health API │  │ OAuth API │                │ │
│  │  └─────┬─────┘  └─────┬─────┘  └─────┬─────┘  └─────┬─────┘                │ │
│  └────────┼──────────────┼──────────────┼──────────────┼────────────────────────┘ │
│           │              │              │              │                        │
│           ▼              ▼              ▼              ▼                        │
│  ┌─────────────────────────────────────────────────────────────────────────────┐ │
│  │                         SERVICE LAYER                                        │ │
│  │  ┌───────────────────────┐  ┌───────────────────────┐                       │ │
│  │  │    Agent Service      │  │     RAG Service       │                       │ │
│  │  │  - process_query()    │  │  - retrieve()         │                       │ │
│  │  │  - get_agents()       │  │  - ingest_file()      │                       │ │
│  │  └───────────┬───────────┘  └───────────┬───────────┘                       │ │
│  └──────────────┼──────────────────────────┼───────────────────────────────────┘ │
│                 │                          │                                     │
│                 ▼                          ▼                                     │
│  ┌─────────────────────────────────────────────────────────────────────────────┐ │
│  │                        ORCHESTRATOR (LangGraph)                              │ │
│  │                                                                              │ │
│  │   ┌─────────┐    ┌─────────────────────────────────────────────────────┐    │ │
│  │   │  Router │───→│              Specialized Agents                     │    │ │
│  │   │  Node   │    │  ┌───────┐ ┌───────┐ ┌───────────┐ ┌─────────────┐  │    │ │
│  │   └─────────┘    │  │Account│ │ Loan  │ │Compliance │ │Notification │  │    │ │
│  │        │         │  │ Agent │ │ Agent │ │   Agent   │ │    Agent    │  │    │ │
│  │        │         │  └───────┘ └───────┘ └───────────┘ └─────────────┘  │    │ │
│  │        │         │  ┌───────┐ ┌───────┐ ┌───────────┐ ┌─────────────┐  │    │ │
│  │        │         │  │Schedule│ │  RAG  │ │Aggregation│ │ BankingData│  │    │ │
│  │        │         │  │ Agent │ │ Agent │ │   Agent   │ │    Agent    │  │    │ │
│  │        │         │  └───────┘ └───────┘ └───────────┘ └─────────────┘  │    │ │
│  │        │         └─────────────────────────────────────────────────────┘    │ │
│  │        │                                  │                                 │ │
│  │        └──────────────────────────────────┼─────────────────────────────────┘ │
│  │                                           │                                  │ │
│  │                                           ▼                                  │ │
│  │                                  ┌─────────────┐                             │ │
│  │                                  │  Response   │                             │ │
│  │                                  │  Formatter  │                             │ │
│  │                                  └──────┬──────┘                             │ │
│  │                                         │                                    │ │
│  └─────────────────────────────────────────┼────────────────────────────────────┘ │
│                                           │                                      │
│                                           ▼                                      │
│  ┌─────────────────────────────────────────────────────────────────────────────┐ │
│  │                          DATA ACCESS LAYER                                   │ │
│  │                                                                              │ │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐        │ │
│  │  │  ChromaDB   │  │   SQLite    │  │    File     │  │  Banking    │        │ │
│  │  │ (Vector DB) │  │  Database   │  │   Storage   │  │   Query     │        │ │
│  │  │             │  │             │  │             │  │  Service    │        │ │
│  │  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘        │ │
│  └─────────────────────────────────────────────────────────────────────────────┘ │
│                                                                                  │
└──────────────────────────────────────────────────────────────────────────────────┘
```

### RAG Pipeline Data Flow:

```
┌──────────────────────────────────────────────────────────────────────────────────┐
│                              RAG PIPELINE                                         │
└──────────────────────────────────────────────────────────────────────────────────┘

INGESTION PHASE:
═══════════════════════════════════════════════════════════════════════════════════

    ┌─────────────┐     ┌─────────────┐     ┌─────────────┐
    │  Upload     │     │  Validate   │     │   Parse     │
    │  File       │────→│  File       │────→│  Content    │
    │  (CSV/XML)  │     │  (.ext,     │     │  (pandas,   │
    │             │     │   size)     │     │   ElementTree)│
    └─────────────┘     └─────────────┘     └──────┬──────┘
                                                   │
                                                   ▼
    ┌─────────────┐     ┌─────────────┐     ┌─────────────┐
    │  Generate   │     │   Chunk     │     │  Process    │
    │  Embeddings │←────│  Text       │←────│  into       │
    │  (Sentence  │     │  (Fixed/    │     │  Chunks     │
    │   Transform)│     │   Semantic) │     │  (Row,      │
    └──────┬──────┘     └─────────────┘     │   Summary,  │
           │                                 │   Column)   │
           │                                 └─────────────┘
           ▼                                 
    ┌─────────────────────────────────────────────────────────────┐
    │                    ChromaDB Vector Store                     │
    │  ┌───────────────────────────────────────────────────────┐  │
    │  │  Collection: "documents"                               │  │
    │  │  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐  │  │
    │  │  │ Doc 1   │  │ Doc 2   │  │ Doc 3   │  │  ...    │  │  │
    │  │  │ [vector]│  │ [vector]│  │ [vector]│  │         │  │  │
    │  │  │ {meta}  │  │ {meta}  │  │ {meta}  │  │         │  │  │
    │  │  └─────────┘  └─────────┘  └─────────┘  └─────────┘  │  │
    │  └───────────────────────────────────────────────────────┘  │
    └─────────────────────────────────────────────────────────────┘

RETRIEVAL PHASE:
═══════════════════════════════════════════════════════════════════════════════════

    User Query: "What are the withdrawal policies?"
                         │
                         ▼
    ┌─────────────┐     ┌─────────────┐     ┌─────────────┐
    │  Generate   │     │  Cosine     │     │  Top-K      │
    │  Query      │────→│  Similarity │────→│  Results    │
    │  Embedding  │     │  Search     │     │  (k=4)      │
    └─────────────┘     └──────┬──────┘     └──────┬──────┘
                               │                    │
                               ▼                    ▼
    ┌─────────────────────────────────────────────────────────────┐
    │                    ChromaDB Vector Store                     │
    │  Query: [0.12, -0.34, 0.56, ...]                            │
    │  ┌───────────────────────────────────────────────────────┐  │
    │  │  Similarity Scores:                                    │  │
    │  │  Doc 3: 0.89 ← Highest match                          │  │
    │  │  Doc 1: 0.76                                          │  │
    │  │  Doc 7: 0.65                                          │  │
    │  │  Doc 2: 0.54                                          │  │
    │  └───────────────────────────────────────────────────────┘  │
    └─────────────────────────────────────────────────────────────┘
                         │
                         ▼
    ┌─────────────┐     ┌─────────────┐     ┌─────────────┐
    │  Build      │     │  LLM        │     │  Return     │
    │  Prompt     │────→│  Generate   │────→│  Response   │
    │  (Context + │     │  (OpenAI/   │     │  with       │
    │  Query)     │     │   Groq)     │     │  Sources    │
    └─────────────┘     └─────────────┘     └─────────────┘
```

---

## 📝 Summary

This Banking Chatbot system is a sophisticated multi-agent application that:

1. **Receives user queries** through a Streamlit web interface
2. **Routes queries** to specialized agents using LangGraph orchestration
3. **Processes banking data** using structured queries and RAG retrieval
4. **Generates responses** using LLMs with document-grounded context
5. **Stores conversations** and file metadata for context awareness
6. **Supports file uploads** with automatic chunking and vectorization
7. **Provides integrations** with OAuth (Google, Slack) and MCP tools

The system is designed for:
- **Scalability**: Lazy loading, modular architecture
- **Reliability**: Error handling, validation, health checks
- **Extensibility**: Easy to add new agents or data sources
- **Performance**: Vector search, caching, efficient data processing