"""
Files API
File upload and management endpoints
"""

from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, status, Query
from pydantic import BaseModel
from typing import Dict, Any, Optional, List
from datetime import datetime
import os
import uuid

from app.core.config import settings
from app.core.logging import get_logger
from app.core.security import get_current_user
from app.utils.file_validator import FileValidator

logger = get_logger(__name__)

router = APIRouter(prefix="/api/files", tags=["Files"])


class FileUploadResponse(BaseModel):
    """Response model for file upload."""
    success: bool
    file_id: str
    filename: str
    file_type: str
    row_count: int
    column_count: int
    chunk_count: int
    columns: List[str]
    message: str
    warnings: Optional[List[str]] = None


class FileInfo(BaseModel):
    """Model for file information."""
    file_id: str
    filename: str
    file_type: str
    uploaded_at: str
    row_count: int
    column_count: int
    size_bytes: int


# In-memory file store (replace with database in production)
uploaded_files: Dict[str, Dict[str, Any]] = {}


@router.post("/upload", response_model=FileUploadResponse)
async def upload_file(
    file: UploadFile = File(...),
    current_user: Optional[dict] = Depends(get_current_user)
):
    """
    Upload a file for RAG ingestion.
    
    Supported file types: CSV, XLSX, XLS, XML
    """
    logger.info(f"Received file upload: {file.filename}")
    
    try:
        # Generate unique file ID
        file_id = str(uuid.uuid4())
        
        # Create upload directory if it doesn't exist
        upload_dir = os.path.join(settings.upload_dir, "raw")
        os.makedirs(upload_dir, exist_ok=True)
        
        # Save uploaded file
        file_path = os.path.join(upload_dir, f"{file_id}_{file.filename}")
        with open(file_path, "wb") as buffer:
            content = await file.read()
            buffer.write(content)
        
        # Validate file
        validation = FileValidator.validate_file(file_path, file.filename)
        if not validation.is_valid:
            # Clean up uploaded file
            os.remove(file_path)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "success": False,
                    "error": "; ".join(validation.errors),
                    "warnings": validation.warnings
                }
            )
        
        # Ingest file to RAG system
        from app.rag.ingestion import ingest_file as ingest_file_to_rag
        ingestion_result = ingest_file_to_rag(
            file_path=file_path,
            original_filename=file.filename
        )
        
        if not ingestion_result.get("success"):
            os.remove(file_path)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail={
                    "success": False,
                    "error": ingestion_result.get("error", "Unknown error during ingestion")
                }
            )
        
        # Store file metadata
        file_metadata = {
            "file_id": file_id,
            "filename": file.filename,
            "file_type": validation.file_type,
            "file_path": file_path,
            "uploaded_at": datetime.now().isoformat(),
            "uploaded_by": current_user.get("sub") if current_user else None,
            "row_count": ingestion_result.get("row_count", 0),
            "column_count": ingestion_result.get("column_count", 0),
            "chunk_count": ingestion_result.get("chunk_count", 0),
            "columns": ingestion_result.get("columns", []),
            "size_bytes": len(content),
            "ingestion_result": ingestion_result
        }
        
        uploaded_files[file_id] = file_metadata
        
        logger.info(f"File uploaded and ingested successfully: {file.filename}")
        
        return FileUploadResponse(
            success=True,
            file_id=file_id,
            filename=file.filename,
            file_type=validation.file_type,
            row_count=ingestion_result.get("row_count", 0),
            column_count=ingestion_result.get("column_count", 0),
            chunk_count=ingestion_result.get("chunk_count", 0),
            columns=ingestion_result.get("columns", []),
            message="File uploaded and processed successfully",
            warnings=validation.warnings
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Error uploading file", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error uploading file: {str(e)}"
        )


@router.get("", response_model=List[Dict[str, Any]])
async def list_files(
    current_user: Optional[dict] = Depends(get_current_user)
):
    """
    List all uploaded files.
    """
    files = []
    for file_id, metadata in uploaded_files.items():
        files.append({
            "file_id": file_id,
            "filename": metadata["filename"],
            "file_type": metadata["file_type"],
            "uploaded_at": metadata["uploaded_at"],
            "row_count": metadata["row_count"],
            "column_count": metadata["column_count"],
            "chunk_count": metadata["chunk_count"],
            "size_bytes": metadata["size_bytes"]
        })
    
    return files


@router.get("/{file_id}", response_model=Dict[str, Any])
async def get_file_info(
    file_id: str,
    current_user: Optional[dict] = Depends(get_current_user)
):
    """
    Get detailed information about a specific file.
    """
    if file_id not in uploaded_files:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File not found"
        )
    
    return uploaded_files[file_id]


@router.delete("/{file_id}")
async def delete_file(
    file_id: str,
    current_user: Optional[dict] = Depends(get_current_user)
):
    """
    Delete an uploaded file.
    """
    if file_id not in uploaded_files:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File not found"
        )
    
    try:
        # Remove physical file
        file_metadata = uploaded_files[file_id]
        if os.path.exists(file_metadata["file_path"]):
            os.remove(file_metadata["file_path"])
        
        # Remove from store
        del uploaded_files[file_id]
        
        logger.info(f"File deleted: {file_id}")
        
        return {"success": True, "message": "File deleted successfully"}
        
    except Exception as e:
        logger.exception("Error deleting file", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error deleting file: {str(e)}"
        )


@router.get("/{file_id}/preview")
async def preview_file(
    file_id: str,
    rows: int = Query(default=10, ge=1, le=100),
    current_user: Optional[dict] = Depends(get_current_user)
):
    """
    Get a preview of the file contents.
    """
    if file_id not in uploaded_files:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File not found"
        )
    
    try:
        import pandas as pd
        
        file_metadata = uploaded_files[file_id]
        file_path = file_metadata["file_path"]
        
        # Read file
        if file_metadata["file_type"] == "csv":
            df = pd.read_csv(file_path, nrows=rows)
        elif file_metadata["file_type"] in {"xlsx", "xls"}:
            df = pd.read_excel(file_path, nrows=rows)
        else:
            import xml.etree.ElementTree as ET

            tree = ET.parse(file_path)
            root = tree.getroot()
            preview_rows = []

            for element in root.iter():
                if len(preview_rows) >= rows:
                    break

                row = {}
                for child in list(element):
                    text = (child.text or "").strip()
                    if text:
                        row[child.tag] = text
                if row:
                    preview_rows.append(row)

        # Convert to dict for response
        if file_metadata["file_type"] in {"csv", "xlsx", "xls"}:
            preview_data = {
                "columns": list(df.columns),
                "data": df.head(rows).to_dict(orient="records"),
                "total_rows": len(df),
                "showing_rows": min(rows, len(df))
            }
        else:
            xml_columns = sorted({key for row_data in preview_rows for key in row_data.keys()})
            preview_data = {
                "columns": xml_columns,
                "data": preview_rows,
                "total_rows": file_metadata.get("row_count", len(preview_rows)),
                "showing_rows": len(preview_rows)
            }

        return preview_data
        
    except Exception as e:
        logger.exception("Error previewing file", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error previewing file: {str(e)}"
        )
