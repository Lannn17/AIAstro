"""Tests for GET /api/region endpoint."""
import os
import sys
import pytest

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from fastapi.testclient import TestClient
from dotenv import load_dotenv
load_dotenv()

from main import app

client = TestClient(app)


def test_region_endpoint_returns_valid_response():
    """GET /api/region should return region: CN or GLOBAL."""
    response = client.get("/api/region")
    assert response.status_code == 200
    data = response.json()
    assert "region" in data
    assert data["region"] in ("CN", "GLOBAL")


def test_region_endpoint_respects_forwarded_for():
    """X-Forwarded-For header should be used for IP lookup."""
    response = client.get("/api/region", headers={"X-Forwarded-For": "8.8.8.8"})
    assert response.status_code == 200
    assert response.json()["region"] == "GLOBAL"
