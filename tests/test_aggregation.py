"""
Aggregation Engine Tests.
"""

import pytest
import pandas as pd
from app.services.aggregation_service import AggregationService


@pytest.fixture
def sample_df():
    return pd.DataFrame({
        "date": ["2024-01-01", "2024-01-15", "2024-02-01", "2024-02-15"],
        "amount": [100.0, 200.0, 300.0, 400.0],
        "category": ["food", "transport", "food", "transport"],
        "user_id": ["u1", "u1", "u2", "u2"],
    })


@pytest.fixture
def svc():
    return AggregationService()


def test_simple_sum(svc, sample_df):
    result = svc.aggregate(sample_df, "amount", "sum")
    assert result["result"] == 1000.0
    assert result["operation"] == "sum"


def test_simple_avg(svc, sample_df):
    result = svc.aggregate(sample_df, "amount", "avg")
    assert result["result"] == 250.0


def test_simple_count(svc, sample_df):
    result = svc.aggregate(sample_df, "amount", "count")
    assert result["result"] == 4


def test_simple_min_max(svc, sample_df):
    assert svc.aggregate(sample_df, "amount", "min")["result"] == 100.0
    assert svc.aggregate(sample_df, "amount", "max")["result"] == 400.0


def test_grouped_sum(svc, sample_df):
    result = svc.aggregate(sample_df, "amount", "sum", group_by=["category"])
    r = result["result"]
    assert isinstance(r, pd.DataFrame)
    assert len(r) == 2
    food_row = r[r["category"] == "food"]
    assert food_row["amount"].values[0] == 400.0


def test_grouped_avg(svc, sample_df):
    result = svc.aggregate(sample_df, "amount", "avg", group_by=["user_id"])
    r = result["result"]
    assert len(r) == 2


def test_filter(svc, sample_df):
    result = svc.aggregate(sample_df, "amount", "sum", filters={"category": "food"})
    assert result["result"] == 400.0


def test_complex_filter(svc, sample_df):
    result = svc.aggregate(sample_df, "amount", "sum", filters={"amount": {"gt": 150}})
    assert result["result"] == 900.0


def test_date_range(svc, sample_df):
    result = svc.aggregate(sample_df, "amount", "sum", date_range=("2024-02-01", "2024-12-31"))
    assert result["result"] == 700.0


def test_duckdb_query(svc, sample_df):
    result = svc.sql_query(sample_df, "SELECT SUM(amount) as total FROM data")
    assert result["success"] is True
    assert result["result"][0]["total"] == 1000.0


def test_natural_language_query(svc, sample_df):
    result = svc.query(sample_df, "total amount")
    assert "result" in result
    assert result["row_count"] >= 0
