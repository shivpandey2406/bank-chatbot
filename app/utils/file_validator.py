"""
File Validator Module
Validates uploaded files for format, size, and content
"""

import os
from pathlib import Path
from typing import List, Tuple, Optional, Dict, Any
import xml.etree.ElementTree as ET

import pandas as pd
from pydantic import BaseModel

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class ValidationResult(BaseModel):
    """Result of file validation."""
    is_valid: bool
    file_type: Optional[str] = None
    file_size: Optional[int] = None
    row_count: Optional[int] = None
    column_count: Optional[int] = None
    columns: Optional[List[str]] = None
    sample_data: Optional[List[Dict[str, Any]]] = None
    errors: List[str] = []
    warnings: List[str] = []


class FileValidator:
    """
    Validates uploaded files for the banking RAG system.
    Supports CSV, Excel, and XML files.
    """

    # Supported file types and their MIME types
    SUPPORTED_TYPES = {
        "csv": ["text/csv", "application/csv"],
        "xlsx": ["application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"],
        "xls": ["application/vnd.ms-excel"],
        "xml": ["application/xml", "text/xml"],
    }

    # Maximum rows for preview
    PREVIEW_ROWS = 5

    @classmethod
    def _allowed_extensions(cls) -> List[str]:
        """Return configured extensions plus built-in XML support."""
        configured = list(settings.allowed_extensions or [])
        if "xml" not in configured:
            configured.append("xml")
        return configured

    @classmethod
    def validate_file(
        cls,
        file_path: str,
        original_filename: str,
        max_size: int = None
    ) -> ValidationResult:
        """
        Validate an uploaded file.

        Args:
            file_path: Path to the uploaded file
            original_filename: Original name of the file
            max_size: Maximum allowed file size in bytes

        Returns:
            ValidationResult with validation details
        """
        max_size = max_size or settings.max_file_size
        errors = []
        warnings = []

        # Check if file exists
        if not os.path.exists(file_path):
            return ValidationResult(
                is_valid=False,
                errors=["File not found"]
            )

        # Get file size
        file_size = os.path.getsize(file_path)

        # Check file size
        if file_size > max_size:
            errors.append(f"File size ({file_size} bytes) exceeds maximum allowed ({max_size} bytes)")

        if file_size == 0:
            errors.append("File is empty")

        # Get file extension
        file_ext = Path(original_filename).suffix.lower().lstrip(".")

        # Check file extension
        allowed_extensions = cls._allowed_extensions()
        if file_ext not in allowed_extensions:
            errors.append(
                f"File type '{file_ext}' is not supported. "
                f"Allowed types: {', '.join(allowed_extensions)}"
            )
            return ValidationResult(
                is_valid=False,
                errors=errors
            )

        # Validate file content based on type
        try:
            if file_ext == "csv":
                return cls._validate_csv(file_path, file_size, errors, warnings)
            elif file_ext in ["xlsx", "xls"]:
                return cls._validate_excel(file_path, file_size, errors, warnings)
            elif file_ext == "xml":
                return cls._validate_xml(file_path, file_size, errors, warnings)
            else:
                errors.append(f"Unsupported file type: {file_ext}")
                return ValidationResult(is_valid=False, errors=errors)
        except Exception as e:
            logger.exception("Error validating file", file_path=file_path, error=str(e))
            errors.append(f"Error reading file: {str(e)}")
            return ValidationResult(is_valid=False, errors=errors)

    @classmethod
    def _validate_csv(
        cls,
        file_path: str,
        file_size: int,
        errors: List[str],
        warnings: List[str]
    ) -> ValidationResult:
        """Validate a CSV file."""
        try:
            df = pd.read_csv(file_path, nrows=100)  # Read first 100 rows for validation
        except Exception as e:
            errors.append(f"Error reading CSV file: {str(e)}")
            return ValidationResult(is_valid=False, errors=errors)

        return cls._create_validation_result(df, "csv", file_size, errors, warnings)

    @classmethod
    def _validate_excel(
        cls,
        file_path: str,
        file_size: int,
        errors: List[str],
        warnings: List[str]
    ) -> ValidationResult:
        """Validate an Excel file."""
        try:
            # Read first sheet
            df = pd.read_excel(file_path, sheet_name=0, nrows=100)
        except Exception as e:
            errors.append(f"Error reading Excel file: {str(e)}")
            return ValidationResult(is_valid=False, errors=errors)

        return cls._create_validation_result(df, "xlsx", file_size, errors, warnings)

    @classmethod
    def _validate_xml(
        cls,
        file_path: str,
        file_size: int,
        errors: List[str],
        warnings: List[str]
    ) -> ValidationResult:
        """Validate an XML file and extract a lightweight structural preview."""
        try:
            tree = ET.parse(file_path)
            root = tree.getroot()
        except Exception as e:
            errors.append(f"Error reading XML file: {str(e)}")
            return ValidationResult(is_valid=False, errors=errors)

        rows = cls._extract_xml_rows(root)
        columns = sorted({key for row in rows for key in row.keys()}) if rows else []

        if not rows:
            warnings.append("XML file contains no repeated record nodes; falling back to text ingestion")

        return ValidationResult(
            is_valid=len(errors) == 0,
            file_type="xml",
            file_size=file_size,
            row_count=len(rows),
            column_count=len(columns),
            columns=columns,
            sample_data=rows[:cls.PREVIEW_ROWS],
            errors=errors,
            warnings=warnings
        )

    @classmethod
    def _extract_xml_rows(cls, root: ET.Element) -> List[Dict[str, Any]]:
        """Extract repeated XML child elements into row-like records."""
        parent_counts: Dict[str, int] = {}
        for child in root.iter():
            for subchild in list(child):
                parent_counts[subchild.tag] = parent_counts.get(subchild.tag, 0) + 1

        repeated_tags = {tag for tag, count in parent_counts.items() if count > 1}
        rows: List[Dict[str, Any]] = []

        for element in root.iter():
            if element.tag not in repeated_tags:
                continue

            row: Dict[str, Any] = {}
            if element.attrib:
                for key, value in element.attrib.items():
                    row[f"@{key}"] = value

            for child in list(element):
                text = (child.text or "").strip()
                if text:
                    row[child.tag] = text
                elif child.attrib:
                    for key, value in child.attrib.items():
                        row[f"{child.tag}.@{key}"] = value

            if row:
                rows.append(row)

        return rows

    @classmethod
    def _create_validation_result(
        cls,
        df: pd.DataFrame,
        file_type: str,
        file_size: int,
        errors: List[str],
        warnings: List[str]
    ) -> ValidationResult:
        """Create a validation result from a DataFrame."""
        row_count = len(df)
        column_count = len(df.columns)
        columns = list(df.columns)

        # Check for empty dataframe
        if row_count == 0:
            warnings.append("File contains no data rows")

        # Check for duplicate column names
        duplicate_cols = [col for col in columns if columns.count(col) > 1]
        if duplicate_cols:
            warnings.append(f"Duplicate column names found: {set(duplicate_cols)}")

        # Check for completely empty columns
        empty_cols = [col for col in columns if df[col].isna().all()]
        if empty_cols:
            warnings.append(f"Completely empty columns: {empty_cols}")

        # Generate sample data
        sample_data = []
        if row_count > 0:
            preview_df = df.head(cls.PREVIEW_ROWS)
            sample_data = preview_df.to_dict(orient="records")

        is_valid = len(errors) == 0

        return ValidationResult(
            is_valid=is_valid,
            file_type=file_type,
            file_size=file_size,
            row_count=row_count,
            column_count=column_count,
            columns=columns,
            sample_data=sample_data,
            errors=errors,
            warnings=warnings
        )

    @classmethod
    def detect_file_type(cls, file_path: str) -> Optional[str]:
        """
        Detect the type of a file based on extension.

        Args:
            file_path: Path to the file

        Returns:
            File type string (csv, xlsx, xls) or None
        """
        ext = Path(file_path).suffix.lower().lstrip(".")
        if ext in cls._allowed_extensions():
            return ext
        return None

    @classmethod
    def get_mime_type(cls, file_type: str) -> Optional[str]:
        """
        Get MIME type for a file type.

        Args:
            file_type: File type string (csv, xlsx, xls)

        Returns:
            MIME type string or None
        """
        mime_types = cls.SUPPORTED_TYPES.get(file_type, [])
        return mime_types[0] if mime_types else None

    @classmethod
    def sanitize_filename(cls, filename: str) -> str:
        """
        Sanitize a filename by removing special characters.

        Args:
            filename: Original filename

        Returns:
            Sanitized filename
        """
        # Remove special characters but keep alphanumeric, dots, hyphens, underscores
        sanitized = "".join(
            c for c in filename
            if c.isalnum() or c in ("-", "_", ".")
        )
        return sanitized.lower()
