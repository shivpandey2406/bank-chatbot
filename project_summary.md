# Banking Chatbot Project Summary

## Overview
A production-grade banking chatbot built with FastAPI, LangGraph multi-agent system, and RAG pipeline. The system features specialized agents for different banking domains (account, loan, compliance, notifications, scheduling) with document-based Q&A capabilities.

## Architecture
- **Backend**: FastAPI with multi-agent orchestration using LangGraph
- **Frontend**: Streamlit web interface
- **Database**: PostgreSQL with SQLite fallback, Redis caching
- **RAG**: ChromaDB vector store with Sentence Transformers embeddings
- **Data Processing**: DuckDB for SQL-like queries on uploaded files
- **Infrastructure**: Docker containerization with docker-compose

## Key Features
- Multi-agent system with specialized banking domain agents
- Document ingestion and semantic search (CSV, Excel support)
- Natural language data aggregation and querying
- File upload and validation system
- OAuth authentication (Google, Slack)
- Email/SMS/Slack notifications
- Appointment scheduling capabilities

## Configuration Requirements
- OpenAI API key for LLM capabilities (gpt-4o-mini, text-embedding-3-small)
- Database connection (PostgreSQL recommended)
- OAuth credentials for authentication
- SMTP settings for email notifications
- Slack bot token for Slack integration
- Redis for caching and task queue

## Free Tier Options
- Use SQLite instead of PostgreSQL for development
- OpenAI free tier for API usage
- Gmail SMTP for email notifications
- Local Redis instance
- No external OAuth required for basic functionality