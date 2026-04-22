"""
Aggregation Service
Handles data aggregation queries on uploaded files
"""

import pandas as pd
import duckdb
from typing import Dict, List, Any, Optional, Union
from pathlib import Path

from app.core.logging import get_logger
from app.rag.structured_query import QueryParser, QueryExecutor, StructuredQuery
from app.utils.date_utils import DateUtils

logger = get_logger(__name__)


class AggregationService:
    """
    Service for performing aggregation operations on data.
    Supports both pandas-based and DuckDB-based queries.
    """

    def __init__(self, use_duckdb: bool = True):
        """
        Initialize aggregation service.

        Args:
            use_duckdb: Whether to use DuckDB for queries (faster for large datasets)
        """
        self.use_duckdb = use_duckdb

    def aggregate(
        self,
        df: pd.DataFrame,
        column: str,
        operation: str,
        group_by: Optional[List[str]] = None,
        filters: Optional[Dict[str, Any]] = None,
        date_range: Optional[tuple] = None
    ) -> Dict[str, Any]:
        """
        Perform aggregation on a DataFrame.

        Args:
            df: Pandas DataFrame
            column: Column to aggregate
            operation: Aggregation operation (sum, avg, count, min, max, etc.)
            group_by: Optional columns to group by
            filters: Optional filter conditions
            date_range: Optional date range tuple (start, end)

        Returns:
            Dictionary with aggregation results
        """
        result_df = df.copy()

        # Apply filters
        if filters:
            result_df = self._apply_filters(result_df, filters)

        # Apply date range
        if date_range:
            result_df = self._apply_date_range(result_df, date_range)

        # Perform aggregation
        if group_by:
            result = self._grouped_aggregate(result_df, column, operation, group_by)
        else:
            result = self._simple_aggregate(result_df, column, operation)

        return {
            "operation": operation,
            "column": column,
            "group_by": group_by,
            "result": result,
            "row_count": len(result_df)
        }

    def query(self, df: pd.DataFrame, natural_query: str) -> Dict[str, Any]:
        """
        Execute a natural language query on a DataFrame.

        Args:
            df: Pandas DataFrame
            natural_query: Natural language query string

        Returns:
            Dictionary with query results
        """
        # Parse the query
        structured_query = QueryParser.parse(natural_query, list(df.columns))

        logger.info(
            "Parsed aggregation query",
            query_type=structured_query.query_type.value,
            aggregations=structured_query.aggregations,
            group_by=structured_query.group_by
        )

        # Execute the query
        result_df = QueryExecutor.execute(structured_query, df)

        # Format the result
        return {
            "query": natural_query,
            "structured_query": structured_query.to_dict(),
            "result": result_df.to_dict(orient="records"),
            "result_df": result_df.to_string(index=False),
            "row_count": len(result_df)
        }

    def sql_query(self, df: pd.DataFrame, sql: str) -> Dict[str, Any]:
        """
        Execute a SQL query on a DataFrame using DuckDB.

        Args:
            df: Pandas DataFrame
            sql: SQL query string

        Returns:
            Dictionary with query results
        """
        if self.use_duckdb:
            return self._duckdb_query(df, sql)
        else:
            return self._pandas_sql_query(df, sql)

    def _simple_aggregate(
        self,
        df: pd.DataFrame,
        column: str,
        operation: str
    ) -> Any:
        """Perform simple aggregation without grouping."""
        if column not in df.columns:
            # Try to find a matching column
            matching_cols = [c for c in df.columns if column.lower() in c.lower()]
            if matching_cols:
                column = matching_cols[0]
            else:
                raise ValueError(f"Column '{column}' not found in DataFrame")

        if operation == "sum":
            return float(df[column].sum())
        elif operation in ("avg", "mean"):
            return float(df[column].mean())
        elif operation == "count":
            return int(df[column].count())
        elif operation == "min":
            return float(df[column].min())
        elif operation == "max":
            return float(df[column].max())
        elif operation == "median":
            return float(df[column].median())
        elif operation == "std":
            return float(df[column].std())
        else:
            raise ValueError(f"Unsupported operation: {operation}")

    def _grouped_aggregate(
        self,
        df: pd.DataFrame,
        column: str,
        operation: str,
        group_by: List[str]
    ) -> pd.DataFrame:
        """Perform aggregation with grouping."""
        # Validate group by columns
        valid_group_cols = []
        for col in group_by:
            if col in df.columns:
                valid_group_cols.append(col)
            else:
                matching = [c for c in df.columns if col.lower() in c.lower()]
                if matching:
                    valid_group_cols.append(matching[0])

        if not valid_group_cols:
            raise ValueError("No valid group by columns found")

        # Validate aggregation column
        if column not in df.columns:
            matching = [c for c in df.columns if column.lower() in c.lower()]
            if matching:
                column = matching[0]
            else:
                raise ValueError(f"Column '{column}' not found")

        # Map operation to pandas agg function
        agg_func = operation
        if operation == "avg":
            agg_func = "mean"

        result = df.groupby(valid_group_cols)[column].agg(agg_func).reset_index()
        return result

    def _apply_filters(
        self,
        df: pd.DataFrame,
        filters: Dict[str, Any]
    ) -> pd.DataFrame:
        """Apply filter conditions to DataFrame."""
        result = df.copy()
        for column, value in filters.items():
            if column in df.columns:
                if isinstance(value, dict):
                    # Support for complex filters like {"gt": 10, "lt": 100}
                    for op, val in value.items():
                        if op == "gt":
                            result = result[result[column] > val]
                        elif op == "lt":
                            result = result[result[column] < val]
                        elif op == "gte":
                            result = result[result[column] >= val]
                        elif op == "lte":
                            result = result[result[column] <= val]
                        elif op == "eq":
                            result = result[result[column] == val]
                        elif op == "ne":
                            result = result[result[column] != val]
                        elif op == "in":
                            result = result[result[column].isin(val)]
                        elif op == "like":
                            result = result[result[column].str.contains(val, na=False)]
                else:
                    result = result[result[column] == value]
        return result

    def _apply_date_range(
        self,
        df: pd.DataFrame,
        date_range: tuple
    ) -> pd.DataFrame:
        """Apply date range filter to DataFrame."""
        start_date, end_date = date_range

        # Find date columns
        date_cols = []
        for col in df.columns:
            col_lower = col.lower()
            if any(p in col_lower for p in ["date", "time"]):
                date_cols.append(col)

        if not date_cols:
            return df

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

    def _duckdb_query(
        self,
        df: pd.DataFrame,
        sql: str
    ) -> Dict[str, Any]:
        """Execute SQL query using DuckDB."""
        try:
            conn = duckdb.connect(":memory:")
            conn.register("data", df)
            result = conn.execute(sql).fetchdf()
            conn.close()

            return {
                "success": True,
                "result": result.to_dict(orient="records"),
                "row_count": len(result)
            }
        except Exception as e:
            logger.exception("DuckDB query error", error=str(e))
            return {
                "success": False,
                "error": str(e)
            }

    def _pandas_sql_query(
        self,
        df: pd.DataFrame,
        sql: str
    ) -> Dict[str, Any]:
        """Execute SQL query using pandas."""
        try:
            # Create a temporary table name
            table_name = "data"

            # Use pandas query method for simple queries
            # For complex SQL, we'd need a proper SQL engine
            result = df.query(sql.replace(table_name, ""))

            return {
                "success": True,
                "result": result.to_dict(orient="records"),
                "row_count": len(result)
            }
        except Exception as e:
            logger.exception("Pandas query error", error=str(e))
            return {
                "success": False,
                "error": str(e)
            }

    def multi_file_aggregate(
        self,
        dataframes: Dict[str, pd.DataFrame],
        query: str
    ) -> Dict[str, Any]:
        """
        Perform aggregation across multiple DataFrames.

        Args:
            dataframes: Dictionary of DataFrame name to DataFrame
            query: Natural language query

        Returns:
            Dictionary with aggregation results
        """
        if self.use_duckdb:
            return self._multi_file_duckdb(dataframes, query)
        else:
            # For pandas, we'd need to merge/join the dataframes
            return {
                "success": False,
                "error": "Multi-file aggregation requires DuckDB"
            }

    def _multi_file_duckdb(
        self,
        dataframes: Dict[str, pd.DataFrame],
        query: str
    ) -> Dict[str, Any]:
        """Execute multi-file query using DuckDB."""
        try:
            conn = duckdb.connect(":memory:")

            # Register all dataframes
            for name, df in dataframes.items():
                conn.register(name, df)

            # Execute query
            result = conn.execute(query).fetchdf()
            conn.close()

            return {
                "success": True,
                "result": result.to_dict(orient="records"),
                "row_count": len(result)
            }
        except Exception as e:
            logger.exception("Multi-file DuckDB query error", error=str(e))
            return {
                "success": False,
                "error": str(e)
            }