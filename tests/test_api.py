"""
API Tests — chat, files, health endpoints.
"""

import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_health():
    r = client.get("/health")
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "healthy"


def test_health_live():
    r = client.get("/health/live")
    assert r.status_code == 200
    assert r.json()["status"] == "alive"


def test_root():
    r = client.get("/")
    assert r.status_code == 200
    assert "Banking" in r.text


def test_chat_message():
    r = client.post("/api/chat/message", json={"message": "hello"})
    assert r.status_code == 200
    data = r.json()
    assert data["success"] is True
    assert "response" in data
    assert "conversation_id" in data


def test_chat_conversation_lifecycle():
    # send message
    r = client.post("/api/chat/message", json={"message": "hi"})
    conv_id = r.json()["conversation_id"]

    # list conversations
    r = client.get("/api/chat/conversations")
    assert r.status_code == 200
    assert any(c["conversation_id"] == conv_id for c in r.json())

    # get conversation
    r = client.get(f"/api/chat/conversation/{conv_id}")
    assert r.status_code == 200
    assert len(r.json()) >= 2  # user + assistant

    # delete
    r = client.delete(f"/api/chat/conversation/{conv_id}")
    assert r.status_code == 200

    # verify gone
    r = client.get(f"/api/chat/conversation/{conv_id}")
    assert r.status_code == 404


def test_chat_agents():
    r = client.get("/api/chat/agents")
    assert r.status_code == 200
    data = r.json()
    assert data["success"] is True
    assert "capabilities" in data
