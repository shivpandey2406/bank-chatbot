"""
Date Utilities Module
Provides date parsing and manipulation utilities for banking queries
"""

import re
from datetime import datetime, timedelta
from typing import Optional, Tuple, Dict, Any

from dateutil import parser as date_parser
from dateutil.relativedelta import relativedelta

from app.core.logging import get_logger

logger = get_logger(__name__)


class DateUtils:
    """
    Utility class for date parsing and manipulation in banking queries.
    Handles natural language date expressions and date range extraction.
    """

    # Common date patterns in natural language
    DATE_PATTERNS = {
        "last_month": r"(?:last|previous)\s+month",
        "this_month": r"(?:this|current)\s+month",
        "next_month": r"next\s+month",
        "last_week": r"(?:last|previous)\s+week",
        "this_week": r"(?:this|current)\s+week",
        "last_year": r"(?:last|previous)\s+year",
        "this_year": r"(?:this|current)\s+year",
        "last_quarter": r"(?:last|previous)\s+quarter",
        "this_quarter": r"(?:this|current)\s+quarter",
        "yesterday": r"yesterday",
        "today": r"today",
        "tomorrow": r"tomorrow",
        "past_days": r"(?:past|last)\s+(\d+)\s+days",
        "past_months": r"(?:past|last)\s+(\d+)\s+months",
        "past_weeks": r"(?:past|last)\s+(\d+)\s+weeks",
    }

    @classmethod
    def parse_date(cls, date_str: str) -> Optional[datetime]:
        """
        Parse a date string into a datetime object.

        Args:
            date_str: Date string in various formats

        Returns:
            Parsed datetime object or None
        """
        if not date_str:
            return None

        try:
            # Try common formats first
            for fmt in ["%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y", "%Y/%m/%d"]:
                try:
                    return datetime.strptime(date_str, fmt)
                except ValueError:
                    continue

            # Use dateutil parser as fallback
            return date_parser.parse(date_str)
        except (ValueError, TypeError) as e:
            logger.warning(f"Failed to parse date: {date_str}", error=str(e))
            return None

    @classmethod
    def extract_date_range(
        cls,
        query: str,
        reference_date: Optional[datetime] = None
    ) -> Tuple[Optional[datetime], Optional[datetime]]:
        """
        Extract date range from a natural language query.

        Args:
            query: Natural language query string
            reference_date: Reference date for relative calculations (defaults to today)

        Returns:
            Tuple of (start_date, end_date) or (None, None) if no date found
        """
        reference_date = reference_date or datetime.now(tz=None)
        query_lower = query.lower()

        # Check for specific date patterns
        for pattern_name, pattern in cls.DATE_PATTERNS.items():
            match = re.search(pattern, query_lower)
            if match:
                return cls._calculate_date_range(pattern_name, match, reference_date)

        # Try to extract explicit dates from the query
        return cls._extract_explicit_dates(query)

    @classmethod
    def _calculate_date_range(
        cls,
        pattern_name: str,
        match: re.Match,
        reference_date: datetime
    ) -> Tuple[Optional[datetime], Optional[datetime]]:
        """Calculate date range based on pattern name."""
        today = reference_date.date()

        if pattern_name == "last_month":
            start = today.replace(day=1) - relativedelta(months=1)
            end = today.replace(day=1) - timedelta(days=1)
            return datetime.combine(start, datetime.min.time()), datetime.combine(end, datetime.max.time())

        elif pattern_name == "this_month":
            start = today.replace(day=1)
            end = today
            return datetime.combine(start, datetime.min.time()), datetime.combine(end, datetime.max.time())

        elif pattern_name == "next_month":
            start = today.replace(day=1) + relativedelta(months=1)
            end = start + relativedelta(months=1) - timedelta(days=1)
            return datetime.combine(start, datetime.min.time()), datetime.combine(end, datetime.max.time())

        elif pattern_name == "last_week":
            # Assuming week starts on Monday
            last_week_start = today - timedelta(days=today.weekday() + 7)
            last_week_end = last_week_start + timedelta(days=6)
            return datetime.combine(last_week_start, datetime.min.time()), datetime.combine(last_week_end, datetime.max.time())

        elif pattern_name == "this_week":
            this_week_start = today - timedelta(days=today.weekday())
            this_week_end = this_week_start + timedelta(days=6)
            return datetime.combine(this_week_start, datetime.min.time()), datetime.combine(this_week_end, datetime.max.time())

        elif pattern_name == "last_year":
            start = today.replace(month=1, day=1) - relativedelta(years=1)
            end = today.replace(month=1, day=1) - timedelta(days=1)
            return datetime.combine(start, datetime.min.time()), datetime.combine(end, datetime.max.time())

        elif pattern_name == "this_year":
            start = today.replace(month=1, day=1)
            end = today
            return datetime.combine(start, datetime.min.time()), datetime.combine(end, datetime.max.time())

        elif pattern_name == "last_quarter":
            # Calculate last quarter
            current_quarter = (today.month - 1) // 3
            if current_quarter == 0:
                quarter_start = today.replace(month=10, day=1) - relativedelta(years=1)
            else:
                quarter_start = today.replace(month=3 * current_quarter - 2, day=1) - relativedelta(months=3)
            quarter_end = quarter_start + relativedelta(months=3) - timedelta(days=1)
            return datetime.combine(quarter_start, datetime.min.time()), datetime.combine(quarter_end, datetime.max.time())

        elif pattern_name == "this_quarter":
            current_quarter = (today.month - 1) // 3
            quarter_start = today.replace(month=3 * current_quarter + 1, day=1)
            quarter_end = today
            return datetime.combine(quarter_start, datetime.min.time()), datetime.combine(quarter_end, datetime.max.time())

        elif pattern_name == "yesterday":
            yesterday = today - timedelta(days=1)
            return datetime.combine(yesterday, datetime.min.time()), datetime.combine(yesterday, datetime.max.time())

        elif pattern_name == "today":
            return datetime.combine(today, datetime.min.time()), datetime.combine(today, datetime.max.time())

        elif pattern_name == "tomorrow":
            tomorrow = today + timedelta(days=1)
            return datetime.combine(tomorrow, datetime.min.time()), datetime.combine(tomorrow, datetime.max.time())

        elif pattern_name == "past_days":
            days = int(match.group(1))
            start = today - timedelta(days=days)
            end = today
            return datetime.combine(start, datetime.min.time()), datetime.combine(end, datetime.max.time())

        elif pattern_name == "past_months":
            months = int(match.group(1))
            start = today - relativedelta(months=months)
            end = today
            return datetime.combine(start, datetime.min.time()), datetime.combine(end, datetime.max.time())

        elif pattern_name == "past_weeks":
            weeks = int(match.group(1))
            start = today - timedelta(weeks=weeks)
            end = today
            return datetime.combine(start, datetime.min.time()), datetime.combine(end, datetime.max.time())

        return None, None

    @classmethod
    def _extract_explicit_dates(cls, query: str) -> Tuple[Optional[datetime], Optional[datetime]]:
        """Extract explicit dates from query."""
        # Look for date patterns like YYYY-MM-DD, MM/DD/YYYY, etc.
        date_patterns = [
            r"\d{4}-\d{2}-\d{2}",  # YYYY-MM-DD
            r"\d{2}/\d{2}/\d{4}",  # MM/DD/YYYY or DD/MM/YYYY
            r"\d{4}/\d{2}/\d{2}",  # YYYY/MM/DD
        ]

        dates_found = []
        for pattern in date_patterns:
            matches = re.findall(pattern, query)
            for match in matches:
                parsed = cls.parse_date(match)
                if parsed:
                    dates_found.append(parsed)

        if len(dates_found) >= 2:
            return dates_found[0], dates_found[-1]
        elif len(dates_found) == 1:
            return dates_found[0], dates_found[0]

        return None, None

    @classmethod
    def format_date_range(
        cls,
        start_date: Optional[datetime],
        end_date: Optional[datetime],
        format_str: str = "%Y-%m-%d"
    ) -> str:
        """
        Format a date range as a string.

        Args:
            start_date: Start date
            end_date: End date
            format_str: Date format string

        Returns:
            Formatted date range string
        """
        if not start_date and not end_date:
            return "All time"

        if start_date and end_date and start_date == end_date:
            return start_date.strftime(format_str)

        parts = []
        if start_date:
            parts.append(start_date.strftime(format_str))
        if end_date:
            parts.append(end_date.strftime(format_str))

        return " to ".join(parts)

    @classmethod
    def get_quarter_dates(
        cls,
        year: int,
        quarter: int
    ) -> Tuple[datetime, datetime]:
        """
        Get start and end dates for a specific quarter.

        Args:
            year: Year
            quarter: Quarter number (1-4)

        Returns:
            Tuple of (start_date, end_date)
        """
        if quarter < 1 or quarter > 4:
            raise ValueError("Quarter must be between 1 and 4")

        start_month = (quarter - 1) * 3 + 1
        start_date = datetime(year, start_month, 1)
        end_date = start_date + relativedelta(months=3) - timedelta(days=1)

        return start_date, end_date

    @classmethod
    def is_date_in_range(
        cls,
        date: datetime,
        start_date: Optional[datetime],
        end_date: Optional[datetime]
    ) -> bool:
        """
        Check if a date falls within a date range.

        Args:
            date: Date to check
            start_date: Range start date
            end_date: Range end date

        Returns:
            True if date is in range
        """
        if start_date and date < start_date:
            return False
        if end_date and date > end_date:
            return False
        return True