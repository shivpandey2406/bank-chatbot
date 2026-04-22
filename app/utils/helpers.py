"""
Helper Utilities Module
General purpose utility functions
"""

import hashlib
import json
import re
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional, Union

from app.core.logging import get_logger

logger = get_logger(__name__)


def generate_uuid() -> str:
    """Generate a new UUID string."""
    return str(uuid.uuid4())


def generate_hash(content: str, algorithm: str = "sha256") -> str:
    """
    Generate a hash of the given content.

    Args:
        content: String content to hash
        algorithm: Hash algorithm to use (default: sha256)

    Returns:
        Hex digest of the hash
    """
    hash_obj = hashlib.new(algorithm)
    hash_obj.update(content.encode("utf-8"))
    return hash_obj.hexdigest()


def truncate_text(text: str, max_length: int = 100, suffix: str = "...") -> str:
    """
    Truncate text to a maximum length.

    Args:
        text: Text to truncate
        max_length: Maximum length
        suffix: Suffix to add if truncated

    Returns:
        Truncated text
    """
    if len(text) <= max_length:
        return text
    return text[: max_length - len(suffix)] + suffix


def sanitize_html(text: str) -> str:
    """
    Remove HTML tags from text.

    Args:
        text: Text potentially containing HTML

    Returns:
        Text with HTML tags removed
    """
    clean = re.compile(r"<[^<]+?>")
    return re.sub(clean, "", text)


def format_number(
    num: Union[int, float],
    decimals: int = 2,
    thousands_separator: bool = True
) -> str:
    """
    Format a number with specified decimal places and optional thousands separator.

    Args:
        num: Number to format
        decimals: Number of decimal places
        thousands_separator: Whether to include thousands separator

    Returns:
        Formatted number string
    """
    if thousands_separator:
        return f"{num:,.{decimals}f}"
    return f"{num:.{decimals}f}"


def format_currency(
    amount: float,
    currency: str = "USD",
    locale: str = "en_US"
) -> str:
    """
    Format an amount as currency.

    Args:
        amount: Amount to format
        currency: Currency code
        locale: Locale for formatting

    Returns:
        Formatted currency string
    """
    symbols = {
        "USD": "$",
        "EUR": "€",
        "GBP": "£",
        "JPY": "¥",
        "INR": "₹",
    }

    symbol = symbols.get(currency, currency + " ")
    formatted = format_number(abs(amount))

    if amount < 0:
        return f"-{symbol}{formatted}"
    return f"{symbol}{formatted}"


def parse_json_safe(json_str: str) -> Any:
    """
    Safely parse a JSON string.

    Args:
        json_str: JSON string to parse

    Returns:
        Parsed object or None if parsing fails
    """
    try:
        return json.loads(json_str)
    except (json.JSONDecodeError, TypeError):
        return None


def to_json(obj: Any, default=str) -> str:
    """
    Convert an object to JSON string.

    Args:
        obj: Object to convert
        default: Default handler for non-serializable objects

    Returns:
        JSON string
    """
    try:
        return json.dumps(obj, default=default, ensure_ascii=False)
    except (TypeError, ValueError) as e:
        logger.warning("Failed to serialize object to JSON", error=str(e))
        return str(obj)


def chunk_list(lst: List[Any], chunk_size: int) -> List[List[Any]]:
    """
    Split a list into chunks of specified size.

    Args:
        lst: List to split
        chunk_size: Size of each chunk

    Returns:
        List of chunks
    """
    return [lst[i : i + chunk_size] for i in range(0, len(lst), chunk_size)]


def flatten_dict(d: Dict, parent_key: str = "", sep: str = ".") -> Dict:
    """
    Flatten a nested dictionary.

    Args:
        d: Dictionary to flatten
        parent_key: Parent key prefix
        sep: Separator for nested keys

    Returns:
        Flattened dictionary
    """
    items = []
    for k, v in d.items():
        new_key = f"{parent_key}{sep}{k}" if parent_key else k
        if isinstance(v, dict):
            items.extend(flatten_dict(v, new_key, sep=sep).items())
        else:
            items.append((new_key, v))
    return dict(items)


def merge_dicts(base: Dict, override: Dict) -> Dict:
    """
    Recursively merge two dictionaries.

    Args:
        base: Base dictionary
        override: Dictionary with values to override

    Returns:
        Merged dictionary
    """
    result = base.copy()
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = merge_dicts(result[key], value)
        else:
            result[key] = value
    return result


def get_nested_value(d: Dict, path: str, default: Any = None) -> Any:
    """
    Get a value from a nested dictionary using a dot-separated path.

    Args:
        d: Dictionary to search
        path: Dot-separated path to the value
        default: Default value if path not found

    Returns:
        Value at path or default
    """
    keys = path.split(".")
    current = d
    for key in keys:
        if isinstance(current, dict) and key in current:
            current = current[key]
        else:
            return default
    return current


def retry_async(
    func,
    max_attempts: int = 3,
    delay: float = 1.0,
    backoff: float = 2.0,
    exceptions: tuple = (Exception,)
):
    """
    Retry an async function with exponential backoff.

    Args:
        func: Async function to retry
        max_attempts: Maximum number of attempts
        delay: Initial delay between attempts
        backoff: Backoff multiplier
        exceptions: Tuple of exceptions to catch

    Returns:
        Result of the function

    Raises:
        Last exception if all attempts fail
    """
    import asyncio

    async def wrapper(*args, **kwargs):
        last_exception = None
        current_delay = delay

        for attempt in range(max_attempts):
            try:
                return await func(*args, **kwargs)
            except exceptions as e:
                last_exception = e
                if attempt < max_attempts - 1:
                    logger.warning(
                        f"Attempt {attempt + 1}/{max_attempts} failed",
                        error=str(e),
                        retry_in=current_delay
                    )
                    await asyncio.sleep(current_delay)
                    current_delay *= backoff

        if last_exception:
            raise last_exception

    return wrapper


def calculate_percentage(
    part: Union[int, float],
    total: Union[int, float],
    decimals: int = 2
) -> float:
    """
    Calculate percentage.

    Args:
        part: Part value
        total: Total value
        decimals: Number of decimal places

    Returns:
        Percentage value
    """
    if total == 0:
        return 0.0
    return round((part / total) * 100, decimals)


def is_valid_email(email: str) -> bool:
    """
    Validate an email address.

    Args:
        email: Email address to validate

    Returns:
        True if valid email format
    """
    pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
    return bool(re.match(pattern, email))


def extract_numbers(text: str) -> List[float]:
    """
    Extract all numbers from a text string.

    Args:
        text: Text to extract numbers from

    Returns:
        List of numbers found
    """
    # Match integers and decimals
    pattern = r"[-+]?\d*\.\d+|\d+"
    matches = re.findall(pattern, text)
    return [float(m) for m in matches]


def batch_process(items: List[Any], batch_size: int, processor):
    """
    Process items in batches.

    Args:
        items: List of items to process
        batch_size: Size of each batch
        processor: Async function to process each batch

    Returns:
        List of results
    """
    batches = chunk_list(items, batch_size)
    results = []
    for batch in batches:
        result = processor(batch)
        results.append(result)
    return results