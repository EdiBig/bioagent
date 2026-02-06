"""
Files router - handles file upload, download, and management

Provides endpoints for:
- Uploading single and multiple files
- Listing user's files from database
- Downloading and previewing files
- Deleting files
- File profiling for bioinformatics data

Security considerations:
- File type validation
- Size limits
- Path traversal prevention
- Secure file storage
"""

import os
import shutil
import hashlib
from pathlib import Path
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from models.database import get_db, User, UploadedFile, get_or_create_user
from models.schemas import FileUpload, FileInfo, APIResponse
from middleware.security import validate_file_extension, ALLOWED_FILE_EXTENSIONS


router = APIRouter(prefix="/files")


# Configuration
UPLOAD_DIR = Path(os.getenv("UPLOAD_DIR", "uploads"))
MAX_FILE_SIZE = int(os.getenv("MAX_FILE_SIZE_MB", "500")) * 1024 * 1024  # Convert to bytes


# ==================== HELPER FUNCTIONS ====================

async def get_current_user(db: AsyncSession) -> User:
    """Get current user from authentication"""
    return await get_or_create_user(
        db,
        email="demo@bioagent.ai",
        full_name="Demo User"
    )


def get_user_upload_dir(user_id: int) -> Path:
    """Get user's upload directory, creating if necessary"""
    user_dir = UPLOAD_DIR / str(user_id)
    user_dir.mkdir(parents=True, exist_ok=True)
    return user_dir


def sanitize_filename(filename: str) -> str:
    """
    Sanitize filename to prevent path traversal attacks.
    """
    # Remove path separators
    filename = filename.replace("/", "").replace("\\", "")
    # Remove null bytes
    filename = filename.replace("\x00", "")
    # Keep only safe characters
    safe_chars = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._-")
    filename = "".join(c if c in safe_chars else "_" for c in filename)
    # Prevent empty or dot-only filenames
    if not filename or filename.startswith("."):
        filename = f"file_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"
    return filename


def get_content_type(filename: str) -> str:
    """Get MIME type based on file extension"""
    extension = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""

    mime_types = {
        # Sequence data
        "fastq": "application/x-fastq",
        "fq": "application/x-fastq",
        "fasta": "application/x-fasta",
        "fa": "application/x-fasta",
        # Alignment data
        "bam": "application/x-bam",
        "sam": "text/x-sam",
        # Variant data
        "vcf": "text/x-vcf",
        "bcf": "application/x-bcf",
        # Annotation data
        "bed": "text/x-bed",
        "gff": "text/x-gff",
        "gtf": "text/x-gtf",
        # Tabular data
        "csv": "text/csv",
        "tsv": "text/tab-separated-values",
        "txt": "text/plain",
        "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        # Compressed
        "gz": "application/gzip",
        "zip": "application/zip",
        # JSON/YAML
        "json": "application/json",
        "yaml": "text/yaml",
        "yml": "text/yaml",
    }

    return mime_types.get(extension, "application/octet-stream")


def detect_file_type(filename: str) -> str:
    """Detect bioinformatics file type from extension"""
    # Handle compressed files
    name = filename.lower()
    if name.endswith('.gz'):
        name = name[:-3]

    ext = name.rsplit(".", 1)[-1] if "." in name else ""

    type_mapping = {
        'fastq': 'fastq', 'fq': 'fastq',
        'fasta': 'fasta', 'fa': 'fasta', 'fna': 'fasta', 'faa': 'fasta',
        'bam': 'bam', 'sam': 'sam', 'cram': 'cram',
        'vcf': 'vcf', 'bcf': 'bcf',
        'bed': 'bed', 'gff': 'gff', 'gtf': 'gtf', 'gff3': 'gff',
        'csv': 'csv', 'tsv': 'tsv', 'txt': 'txt',
        'h5ad': 'h5ad', 'mtx': 'mtx', 'loom': 'loom',
        'pdb': 'pdb', 'cif': 'cif', 'mmcif': 'cif',
        'json': 'json', 'yaml': 'yaml', 'yml': 'yaml',
        'parquet': 'parquet', 'bw': 'bigwig', 'bigwig': 'bigwig',
    }

    return type_mapping.get(ext, 'unknown')


def calculate_checksum(file_path: Path) -> str:
    """Calculate SHA256 checksum of a file"""
    sha256 = hashlib.sha256()
    with open(file_path, 'rb') as f:
        for chunk in iter(lambda: f.read(8192), b''):
            sha256.update(chunk)
    return sha256.hexdigest()


# ==================== UPLOAD ENDPOINTS ====================

@router.post("/upload", response_model=APIResponse)
async def upload_file(
    file: UploadFile = File(...),
    description: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
):
    """
    Upload a single file.

    Validates file type and size, stores file, and creates database record.
    """
    user = await get_current_user(db)

    # Validate file extension
    if not validate_file_extension(file.filename, ALLOWED_FILE_EXTENSIONS):
        raise HTTPException(
            status_code=400,
            detail=f"File type not allowed. Allowed types: {', '.join(sorted(ALLOWED_FILE_EXTENSIONS))}"
        )

    # Sanitize filename
    original_filename = file.filename
    safe_filename = sanitize_filename(file.filename)

    # Check file size (read in chunks to avoid memory issues)
    file_size = 0
    temp_path = UPLOAD_DIR / f"temp_{user.id}_{safe_filename}"

    try:
        UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

        with open(temp_path, "wb") as buffer:
            while chunk := await file.read(8192):  # 8KB chunks
                file_size += len(chunk)
                if file_size > MAX_FILE_SIZE:
                    buffer.close()
                    temp_path.unlink()
                    raise HTTPException(
                        status_code=413,
                        detail=f"File too large. Maximum size: {MAX_FILE_SIZE // (1024*1024)}MB"
                    )
                buffer.write(chunk)

        # Move to final location
        user_dir = get_user_upload_dir(user.id)
        final_path = user_dir / safe_filename

        # Handle duplicate filenames
        if final_path.exists():
            name, ext = safe_filename.rsplit(".", 1) if "." in safe_filename else (safe_filename, "")
            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            safe_filename = f"{name}_{timestamp}.{ext}" if ext else f"{name}_{timestamp}"
            final_path = user_dir / safe_filename

        shutil.move(str(temp_path), str(final_path))

        # Calculate checksum
        checksum = calculate_checksum(final_path)

        # Detect file type
        file_type = detect_file_type(original_filename)
        content_type = get_content_type(safe_filename)

        # Create database record
        db_file = UploadedFile(
            user_id=user.id,
            filename=safe_filename,
            original_filename=original_filename,
            file_path=str(final_path),
            file_size=file_size,
            file_type=file_type,
            content_type=content_type,
            description=description,
            checksum=checksum,
        )
        db.add(db_file)
        await db.flush()
        await db.refresh(db_file)

        return APIResponse(
            message="File uploaded successfully",
            data={
                "id": db_file.id,
                "filename": safe_filename,
                "original_filename": original_filename,
                "file_type": file_type,
                "file_size": file_size,
                "content_type": content_type,
                "created_at": db_file.created_at.isoformat(),
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        # Cleanup on error
        if temp_path.exists():
            temp_path.unlink()
        raise HTTPException(
            status_code=500,
            detail=f"Upload failed: {str(e)}"
        )


@router.post("/upload-multiple", response_model=APIResponse)
async def upload_multiple_files(
    files: List[UploadFile] = File(...),
    db: AsyncSession = Depends(get_db)
):
    """
    Upload multiple files at once.

    Returns list of successfully uploaded files and any failures.
    """
    user = await get_current_user(db)

    uploaded = []
    failed = []

    for file in files:
        try:
            # Validate file extension
            if not validate_file_extension(file.filename, ALLOWED_FILE_EXTENSIONS):
                failed.append({
                    "filename": file.filename,
                    "error": "File type not allowed"
                })
                continue

            # Sanitize filename
            original_filename = file.filename
            safe_filename = sanitize_filename(file.filename)

            # Read file content
            content = await file.read()
            file_size = len(content)

            if file_size > MAX_FILE_SIZE:
                failed.append({
                    "filename": file.filename,
                    "error": f"File too large (max {MAX_FILE_SIZE // (1024*1024)}MB)"
                })
                continue

            # Save file
            user_dir = get_user_upload_dir(user.id)
            final_path = user_dir / safe_filename

            # Handle duplicates
            if final_path.exists():
                name, ext = safe_filename.rsplit(".", 1) if "." in safe_filename else (safe_filename, "")
                timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
                safe_filename = f"{name}_{timestamp}.{ext}" if ext else f"{name}_{timestamp}"
                final_path = user_dir / safe_filename

            with open(final_path, "wb") as f:
                f.write(content)

            # Calculate checksum
            checksum = hashlib.sha256(content).hexdigest()

            # Detect file type
            file_type = detect_file_type(original_filename)
            content_type = get_content_type(safe_filename)

            # Create database record
            db_file = UploadedFile(
                user_id=user.id,
                filename=safe_filename,
                original_filename=original_filename,
                file_path=str(final_path),
                file_size=file_size,
                file_type=file_type,
                content_type=content_type,
                checksum=checksum,
            )
            db.add(db_file)
            await db.flush()
            await db.refresh(db_file)

            uploaded.append({
                "id": db_file.id,
                "filename": safe_filename,
                "original_filename": original_filename,
                "file_type": file_type,
                "file_size": file_size,
            })

        except Exception as e:
            failed.append({
                "filename": file.filename,
                "error": str(e)
            })

    return APIResponse(
        message=f"Uploaded {len(uploaded)} files, {len(failed)} failed",
        data={"uploaded": uploaded, "failed": failed}
    )


# ==================== LIST/GET ENDPOINTS ====================

@router.get("/list")
async def list_files(
    skip: int = 0,
    limit: int = 50,
    file_type: Optional[str] = Query(None, description="Filter by file type"),
    db: AsyncSession = Depends(get_db)
):
    """
    List user's uploaded files from database.

    Optional filtering by file type.
    """
    user = await get_current_user(db)

    # Build query
    stmt = select(UploadedFile).where(
        UploadedFile.user_id == user.id,
        UploadedFile.is_deleted == False
    )

    if file_type:
        stmt = stmt.where(UploadedFile.file_type == file_type.lower())

    # Order by most recent first
    stmt = stmt.order_by(UploadedFile.created_at.desc()).offset(skip).limit(limit)

    result = await db.execute(stmt)
    files = result.scalars().all()

    return [
        {
            "id": f.id,
            "filename": f.filename,
            "original_filename": f.original_filename,
            "file_type": f.file_type,
            "file_size": f.file_size,
            "content_type": f.content_type,
            "description": f.description,
            "is_profiled": f.is_profiled,
            "profile_data": f.profile_data,
            "created_at": f.created_at.isoformat(),
        }
        for f in files
    ]


@router.get("/{file_id}")
async def get_file_info(
    file_id: int,
    db: AsyncSession = Depends(get_db)
):
    """Get detailed info about a specific file"""
    user = await get_current_user(db)

    stmt = select(UploadedFile).where(
        UploadedFile.id == file_id,
        UploadedFile.user_id == user.id,
        UploadedFile.is_deleted == False
    )
    result = await db.execute(stmt)
    file = result.scalar_one_or_none()

    if not file:
        raise HTTPException(status_code=404, detail="File not found")

    return {
        "id": file.id,
        "filename": file.filename,
        "original_filename": file.original_filename,
        "file_type": file.file_type,
        "file_size": file.file_size,
        "content_type": file.content_type,
        "description": file.description,
        "checksum": file.checksum,
        "is_profiled": file.is_profiled,
        "profile_data": file.profile_data,
        "created_at": file.created_at.isoformat(),
        "updated_at": file.updated_at.isoformat(),
    }


@router.get("/download/{file_id}")
async def download_file(
    file_id: int,
    db: AsyncSession = Depends(get_db)
):
    """Download a file by ID"""
    user = await get_current_user(db)

    stmt = select(UploadedFile).where(
        UploadedFile.id == file_id,
        UploadedFile.user_id == user.id,
        UploadedFile.is_deleted == False
    )
    result = await db.execute(stmt)
    file = result.scalar_one_or_none()

    if not file:
        raise HTTPException(status_code=404, detail="File not found")

    file_path = Path(file.file_path)
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found on disk")

    return FileResponse(
        path=file_path,
        filename=file.original_filename,
        media_type=file.content_type or "application/octet-stream"
    )


@router.get("/preview/{file_id}", response_model=APIResponse)
async def preview_file(
    file_id: int,
    lines: int = Query(50, ge=1, le=1000, description="Number of lines to preview"),
    db: AsyncSession = Depends(get_db)
):
    """Preview file contents (first N lines)"""
    user = await get_current_user(db)

    stmt = select(UploadedFile).where(
        UploadedFile.id == file_id,
        UploadedFile.user_id == user.id,
        UploadedFile.is_deleted == False
    )
    result = await db.execute(stmt)
    file = result.scalar_one_or_none()

    if not file:
        raise HTTPException(status_code=404, detail="File not found")

    file_path = Path(file.file_path)
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found on disk")

    # Check if file is text-based
    text_types = {"txt", "csv", "tsv", "vcf", "bed", "gff", "gtf", "sam", "fasta", "json", "yaml"}
    if file.file_type not in text_types:
        raise HTTPException(
            status_code=400,
            detail="Preview not available for binary files"
        )

    try:
        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            preview_lines = []
            for i, line in enumerate(f):
                if i >= lines:
                    break
                preview_lines.append(line.rstrip("\n"))

        return APIResponse(
            message="File preview",
            data={
                "lines": preview_lines,
                "truncated": len(preview_lines) == lines
            }
        )

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to read file: {str(e)}"
        )


# ==================== DELETE ENDPOINT ====================

@router.delete("/delete/{file_id}", response_model=APIResponse)
async def delete_file(
    file_id: int,
    db: AsyncSession = Depends(get_db)
):
    """
    Delete a file (soft delete in DB, remove from disk).
    """
    user = await get_current_user(db)

    stmt = select(UploadedFile).where(
        UploadedFile.id == file_id,
        UploadedFile.user_id == user.id,
        UploadedFile.is_deleted == False
    )
    result = await db.execute(stmt)
    file = result.scalar_one_or_none()

    if not file:
        raise HTTPException(status_code=404, detail="File not found")

    try:
        # Remove from disk
        file_path = Path(file.file_path)
        if file_path.exists():
            file_path.unlink()

        # Soft delete in database
        file.is_deleted = True

        return APIResponse(message=f"File {file.original_filename} deleted successfully")
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to delete file: {str(e)}"
        )


# ==================== STATS ENDPOINT ====================

@router.get("/stats/summary", response_model=APIResponse)
async def get_file_stats(
    db: AsyncSession = Depends(get_db)
):
    """Get file statistics for the current user"""
    user = await get_current_user(db)

    # Total files
    total_stmt = select(func.count(UploadedFile.id)).where(
        UploadedFile.user_id == user.id,
        UploadedFile.is_deleted == False
    )
    total_result = await db.execute(total_stmt)
    total = total_result.scalar() or 0

    # Total size
    size_stmt = select(func.sum(UploadedFile.file_size)).where(
        UploadedFile.user_id == user.id,
        UploadedFile.is_deleted == False
    )
    size_result = await db.execute(size_stmt)
    total_size = size_result.scalar() or 0

    # Files by type
    type_stmt = select(
        UploadedFile.file_type,
        func.count(UploadedFile.id)
    ).where(
        UploadedFile.user_id == user.id,
        UploadedFile.is_deleted == False
    ).group_by(UploadedFile.file_type)
    type_result = await db.execute(type_stmt)
    by_type = {row[0] or 'unknown': row[1] for row in type_result.all()}

    return APIResponse(
        message="File statistics",
        data={
            "total_files": total,
            "total_size_bytes": total_size,
            "total_size_mb": round(total_size / (1024 * 1024), 2),
            "by_type": by_type,
        }
    )
