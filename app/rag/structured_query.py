"""
Structured Query Module
Converts natural language queries to structured database queries
"""

import re
from typing import Dict, List, Any, Optional, Tuple
from enum import Enum

import pandas as pd

from app.core.logging import get_logger
from app.utils.date_utils import DateUtils

logger = get_logger(__name__)


class QueryType(str, Enum):
    """Types of queries that can be generated."""
    AGGREGATION = "aggregation"
    FILTER = "filter"
    GROUP_BY = "group_by"
    SELECT = "select"
    UNKNOWN = "unknown"


class AggregationOperation(str, Enum):
    """Supported aggregation operations."""
    SUM = "sum"
    AVG = "avg"
    MEAN = "mean"
    COUNT = "count"
    MIN = "min"
    MAX = "max"
    MEDIAN = "median"
    STD = "std"


class StructuredQuery:
    """
    Represents a structured query parsed from natural language.
    """

    def __init__(
        self,
        query_type: QueryType,
        columns: Optional[List[str]] = None,
        filters: Optional[Dict[str, Any]] = None,
        aggregations: Optional[Dict[str, str]] = None,
        group_by: Optional[List[str]] = None,
        order_by: Optional[List[Tuple[str, str]]] = None,
        limit: Optional[int] = None,
        date_range: Optional[Tuple[str, str]] = None,
        original_query: str = ""
    ):
        self.query_type = query_type
        self.columns = columns or []
        self.filters = filters or {}
        self.aggregations = aggregations or {}
        self.group_by = group_by or []
        self.order_by = order_by or []
        self.limit = limit
        self.date_range = date_range
        self.original_query = original_query

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "query_type": self.query_type.value,
            "columns": self.columns,
            "filters": self.filters,
            "aggregations": self.aggregations,
            "group_by": self.group_by,
            "order_by": self.order_by,
            "limit": self.limit,
            "date_range": self.date_range,
            "original_query": self.original_query
        }

    def __repr__(self) -> str:
        return f"<StructuredQuery(type={self.query_type.value}, columns={self.columns})>"


class QueryParser:
    """
    Parses natural language queries into structured queries.
    Uses pattern matching and keyword detection.
    """

    # Aggregation keywords
    AGGREGATION_KEYWORDS = {
        "sum": AggregationOperation.SUM,
        "total": AggregationOperation.SUM,
        "average": AggregationOperation.AVG,
        "avg": AggregationOperation.AVG,
        "mean": AggregationOperation.AVG,
        "count": AggregationOperation.COUNT,
        "how many": AggregationOperation.COUNT,
        "number of": AggregationOperation.COUNT,
        "min": AggregationOperation.MIN,
        "minimum": AggregationOperation.MIN,
        "max": AggregationOperation.MAX,
        "maximum": AggregationOperation.MAX,
        "median": AggregationOperation.MEDIAN,
        "std": AggregationOperation.STD,
        "standard deviation": AggregationOperation.STD,
    }

    # Group by keywords
    GROUP_BY_KEYWORDS = ["group by", "per", "by", "by each", "for each"]

    # Order by keywords
    ORDER_BY_KEYWORDS = ["order by", "sort by", "top", "bottom", "highest", "lowest"]

    # Filter keywords
    FILTER_KEYWORDS = ["where", "with", "that", "which", "in", "from"]

    # Date column patterns
    DATE_COLUMN_PATTERNS = [
        r"\bdate\b", r"\btime\b", r"\bcreated\b", r"\bupdated\b",
        r"\btransaction_date\b", r"\bposted_date\b"
    ]

    @classmethod
    def parse(cls, query: str, columns: Optional[List[str]] = None) -> StructuredQuery:
        """
        Parse a natural language query into a structured query.

        Args:
            query: Natural language query
            columns: Available column names for context

        Returns:
            StructuredQuery object
        """
        query_lower = query.lower().strip()

        # Detect query type and components
        query_type = QueryType.UNKNOWN
        aggregations = {}
        group_by = []
        filters = {}
        order_by = []
        limit = None
        date_range = None
        selected_columns = []

        # Check for aggregation
        detected_agg = cls._detect_aggregations(query_lower)
        if detected_agg:
            aggregations = detected_agg
            query_type = QueryType.AGGREGATION

        # Check for group by
        detected_group = cls._detect_group_by(query_lower, columns)
        if detected_group:
            group_by = detected_group
            query_type = QueryType.GROUP_BY

        # Check for date range
        detected_date = DateUtils.extract_date_range(query)
        if detected_date[0] or detected_date[1]:
            date_range = (
                detected_date[0].isoformat() if detected_date[0] else None,
                detected_date[1].isoformat() if detected_date[1] else None
            )

        # Check for limit (top N)
        detected_limit = cls._detect_limit(query_lower)
        if detected_limit:
            limit = detected_limit
            order_by = [(list(aggregations.keys())[0] if aggregations else "value", "desc")]

        # Extract column references
        if columns:
            selected_columns = cls._extract_columns(query_lower, columns)

        # Build structured query
        return StructuredQuery(
            query_type=query_type,
            columns=selected_columns,
            filters=filters,
            aggregations=aggregations,
            group_by=group_by,
            order_by=order_by,
            limit=limit,
            date_range=date_range,
            original_query=query
        )

    @classmethod
    def _detect_aggregations(cls, query: str) -> Dict[str, str]:
        """Detect aggregation operations in query."""
        aggregations = {}

        for keyword, operation in cls.AGGREGATION_KEYWORDS.items():
            if keyword in query:
                # Try to find the column being aggregated
                # Look for patterns like "sum of X", "total X", etc.
                patterns = [
                    rf"{keyword}\s+of\s+(\w+)",
                    rf"{keyword}\s+(\w+)",
                ]

                for pattern in patterns:
                    match = re.search(pattern, query)
                    if match:
                        column = match.group(1)
                        aggregations[column] = operation.value
                        break

                # If no column found, mark as needing column detection
                if not aggregations:
                    aggregations["unknown"] = operation.value

        return aggregations

    @classmethod
    def _detect_group_by(cls, query: str, columns: Optional[List[str]]) -> List[str]:
        """Detect group by columns in query."""
        group_by = []

        for keyword in cls.GROUP_BY_KEYWORDS:
            if keyword in query:
                # Look for column after keyword
                pattern = rf"{keyword}\s+(\w+)"
                match = re.search(pattern, query)
                if match:
                    group_by.append(match.group(1))

                # Check if any known columns are mentioned
                if columns:
                    for col in columns:
                        if col.lower() in query and col.lower() not in group_by:
                            # Check if it's near a group by keyword
                            idx = query.find(keyword)
                            if idx >= 0 and col.lower() in query[idx:]:
                                group_by.append(col)

        return group_by

    @classmethod
    def _detect_limit(cls, query: str) -> Optional[int]:
        """Detect limit in query (e.g., 'top 10', 'first 5')."""
        patterns = [
            r"\btop\s+(\d+)\b",
            r"\bfirst\s+(\d+)\b",
            r"\blast\s+(\d+)\b",
            r"\b(\d+)\s+most\b",
        ]

        for pattern in patterns:
            match = re.search(pattern, query)
            if match:
                return int(match.group(1))

        return None

    @classmethod
    def _extract_columns(cls, query: str, columns: List[str]) -> List[str]:
        """Extract column references from query."""
        found_columns = []
        query_lower = query.lower()

        for col in columns:
            if col.lower() in query_lower:
                found_columns.append(col)

        return found_columns


class QueryExecutor:
    """
    Executes structured queries on pandas DataFrames.
    """

    @staticmethod
    def execute(structured_query: StructuredQuery, df: pd.DataFrame) -> pd.DataFrame:
        """
        Execute a structured query on a DataFrame.

        Args:
            structured_query: Parsed structured query
            df: Pandas DataFrame to query

        Returns:
            Result DataFrame
        """
        result = df.copy()

        # Apply date filters
        if structured_query.date_range:
            result = QueryExecutor._apply_date_filter(
                result,
                structured_query.date_range
            )

        # Apply aggregations
        if structured_query.aggregations:
            result = QueryExecutor._apply_aggregations(
                result,
                structured_query.aggregations,
                structured_query.group_by
            )

        # Apply ordering
        if structured_query.order_by:
            result = QueryExecutor._apply_ordering(
                result,
                structured_query.order_by
            )

        # Apply limit
        if structured_query.limit:
            result = result.head(structured_query.limit)

        return result

    @staticmethod
    def _apply_date_filter(
        df: pd.DataFrame,
        date_range: Tuple[str, str]
    ) -> pd.DataFrame:
        """Apply date range filter to DataFrame."""
        start_date, end_date = date_range

        # Find date columns
        date_cols = []
        for col in df.columns:
            col_lower = col.lower()
            if any(pattern in col_lower for pattern in ["date", "time"]):
                date_cols.append(col)

        if not date_cols:
            return df

        # Use the first date column found
        date_col = date_cols[0]

        # Convert to datetime if needed
        if not pd.api.types.is_datetime64_any_dtype(df[date_col]):
            df[date_col] = pd.to_datetime(df[date_col], errors="coerce")

        # Apply filters
        if start_date:
            df = df[df[date_col] >= pd.to_datetime(start_date)]
        if end_date:
            df = df[df[date_col] <= pd.to_datetime(end_date)]

        return df

    @staticmethod
    def _apply_aggregations(
        df: pd.DataFrame,
        aggregations: Dict[str, str],
        group_by: List[str]
    ) -> pd.DataFrame:
        """Apply aggregation operations to DataFrame."""
        if group_by:
            # Group by specified columns
            grouped = df.groupby(group_by)

            # Build aggregation dict
            agg_dict = {}
            for col, op in aggregations.items():
                if col in df.columns:
                    agg_dict[col] = op

            if agg_dict:
                result = grouped.agg(agg_dict)
            else:
                result = grouped.size().reset_index(name="count")

            return result.reset_index()
        else:
            # Simple aggregation without grouping
            results = {}
            for col, op in aggregations.items():
                if col in df.columns:
                    if op == "sum":
                        results[col] = df[col].sum()
                    elif op in ("avg", "mean"):
                        results[col] = df[col].mean()
                    elif op == "count":
                        results[col] = df[col].count()
                    elif op == "min":
                        results[col] = df[col].min()
                    elif op == "max":
                        results[col] = df[col].max()
                    elif op == "median":
                        results[col] = df[col].median()
                    elif op == "std":
                        results[col] = df[col].std()

            return pd.DataFrame([results])

    @staticmethod
    def _apply_ordering(
        df: pd.DataFrame,
        order_by: List[Tuple[str, str]]
    ) -> pd.DataFrame:
        """Apply ordering to DataFrame."""
        for col, direction in order_by:
            if col in df.columns:
                ascending = direction.lower() != "desc"
                df = df.sort_values(by=col, ascending=ascending)

        return df