"""
Analyses router - handles bioinformatics analysis tracking

Provides endpoints for:
- Creating and managing analyses
- Tracking analysis progress
- Retrieving analysis results
- Getting analysis statistics
"""

from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Body
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from models.database import get_db, Analysis, User, ChatSession, UploadedFile, get_or_create_user
from models.schemas import (
    AnalysisCreate, Analysis as AnalysisSchema,
    AnalysisStatus, AnalysisType, AnalysisStats,
    APIResponse, PaginatedResponse
)


router = APIRouter(prefix="/analyses")


# ==================== HELPER FUNCTIONS ====================

async def get_current_user(db: AsyncSession) -> User:
    """Get current user from authentication"""
    return await get_or_create_user(
        db,
        email="demo@bioagent.ai",
        full_name="Demo User"
    )


# ==================== HELPER: Generate BIO-style ID ====================

async def generate_analysis_id(db: AsyncSession, user_id: int) -> str:
    """Generate a unique BIO-YYYYMMDD-NNN analysis ID"""
    today = datetime.utcnow().strftime("%Y%m%d")
    prefix = f"BIO-{today}-"

    # Count existing analyses today
    count_stmt = select(func.count(Analysis.id)).where(
        Analysis.user_id == user_id,
        Analysis.analysis_id.like(f"{prefix}%")
    )
    result = await db.execute(count_stmt)
    count = result.scalar() or 0

    # Generate sequence number
    sequence = str(count + 1).zfill(3)
    return f"{prefix}{sequence}"


# ==================== CREATE/GET ENDPOINTS ====================

@router.post("", response_model=APIResponse)
async def create_analysis(
    analysis_data: AnalysisCreate,
    chat_session_id: Optional[int] = None,
    db: AsyncSession = Depends(get_db)
):
    """
    Create a new analysis record.

    Can optionally be linked to a chat session.
    """
    user = await get_current_user(db)

    # Generate BIO-style ID
    analysis_id = await generate_analysis_id(db, user.id)

    # Verify chat session if provided
    if chat_session_id:
        session_stmt = select(ChatSession).where(
            ChatSession.id == chat_session_id,
            ChatSession.user_id == user.id
        )
        session_result = await db.execute(session_stmt)
        if not session_result.scalar_one_or_none():
            raise HTTPException(status_code=404, detail="Chat session not found")

    new_analysis = Analysis(
        user_id=user.id,
        analysis_id=analysis_id,
        chat_session_id=chat_session_id,
        title=analysis_data.title,
        description=analysis_data.description,
        analysis_type=analysis_data.analysis_type.value,
        input_files=analysis_data.input_files,
        status="pending"
    )

    db.add(new_analysis)
    await db.flush()
    await db.refresh(new_analysis)

    return APIResponse(
        message="Analysis created successfully",
        data={
            "id": new_analysis.id,
            "analysis_id": new_analysis.analysis_id,
            "title": new_analysis.title,
            "description": new_analysis.description,
            "analysis_type": new_analysis.analysis_type,
            "status": new_analysis.status,
            "input_files": new_analysis.input_files,
            "created_at": new_analysis.created_at.isoformat(),
        }
    )


@router.post("/start-with-files", response_model=APIResponse)
async def start_analysis_with_files(
    file_ids: List[int] = Body(..., embed=True),
    analysis_type: str = Body("general", embed=True),
    title: Optional[str] = Body(None, embed=True),
    description: Optional[str] = Body(None, embed=True),
    db: AsyncSession = Depends(get_db)
):
    """
    Start a new analysis with selected files.

    Creates an Analysis record and a linked ChatSession, then returns
    the chat session ID for the frontend to redirect to.
    """
    user = await get_current_user(db)

    if not file_ids:
        raise HTTPException(status_code=400, detail="At least one file must be selected")

    # Verify files exist and belong to user
    files_stmt = select(UploadedFile).where(
        UploadedFile.id.in_(file_ids),
        UploadedFile.user_id == user.id,
        UploadedFile.is_deleted == False
    )
    result = await db.execute(files_stmt)
    files = result.scalars().all()

    if len(files) != len(file_ids):
        raise HTTPException(status_code=404, detail="One or more files not found")

    # Generate analysis ID
    analysis_id = await generate_analysis_id(db, user.id)

    # Generate title from files if not provided
    if not title:
        file_names = [f.original_filename for f in files[:3]]
        if len(files) > 3:
            title = f"Analysis of {', '.join(file_names)} +{len(files)-3} more"
        else:
            title = f"Analysis of {', '.join(file_names)}"
        if len(title) > 100:
            title = title[:97] + "..."

    # Build input files list with metadata
    input_files = [
        {
            "id": f.id,
            "filename": f.original_filename,
            "file_type": f.file_type,
            "file_size": f.file_size,
            "file_path": f.file_path,
        }
        for f in files
    ]

    # Create chat session first
    chat_title = f"{analysis_id}: {title[:50]}"
    new_session = ChatSession(
        user_id=user.id,
        title=chat_title
    )
    db.add(new_session)
    await db.flush()
    await db.refresh(new_session)

    # Create analysis linked to chat session
    new_analysis = Analysis(
        user_id=user.id,
        analysis_id=analysis_id,
        chat_session_id=new_session.id,
        title=title,
        description=description,
        analysis_type=analysis_type,
        input_files=input_files,
        status="pending"
    )
    db.add(new_analysis)
    await db.flush()
    await db.refresh(new_analysis)

    return APIResponse(
        message="Analysis started successfully",
        data={
            "analysis_id": new_analysis.analysis_id,
            "analysis_db_id": new_analysis.id,
            "chat_session_id": new_session.id,
            "title": new_analysis.title,
            "files": [f.original_filename for f in files],
            "redirect_url": f"/chat/{new_session.id}",
        }
    )


@router.get("", response_model=PaginatedResponse)
async def list_analyses(
    skip: int = 0,
    limit: int = 20,
    analysis_type: Optional[AnalysisType] = None,
    status: Optional[AnalysisStatus] = None,
    db: AsyncSession = Depends(get_db)
):
    """
    List user's analyses with optional filtering.

    Supports filtering by analysis type and status.
    """
    user = await get_current_user(db)

    # Build query
    stmt = select(Analysis).where(Analysis.user_id == user.id)

    if analysis_type:
        stmt = stmt.where(Analysis.analysis_type == analysis_type.value)

    if status:
        stmt = stmt.where(Analysis.status == status.value)

    # Get total count
    count_stmt = select(func.count(Analysis.id)).where(Analysis.user_id == user.id)
    if analysis_type:
        count_stmt = count_stmt.where(Analysis.analysis_type == analysis_type.value)
    if status:
        count_stmt = count_stmt.where(Analysis.status == status.value)

    total_result = await db.execute(count_stmt)
    total = total_result.scalar()

    # Get paginated results
    stmt = stmt.order_by(Analysis.created_at.desc()).offset(skip).limit(limit)
    result = await db.execute(stmt)
    analyses = result.scalars().all()

    return PaginatedResponse(
        items=[
            {
                "id": a.id,
                "analysis_id": a.analysis_id,
                "title": a.title,
                "description": a.description,
                "analysis_type": a.analysis_type,
                "status": a.status,
                "input_files": a.input_files,
                "output_files": a.output_files,
                "results_summary": a.results_summary,
                "chat_session_id": a.chat_session_id,
                "created_at": a.created_at.isoformat() if a.created_at else None,
                "started_at": a.started_at.isoformat() if a.started_at else None,
                "completed_at": a.completed_at.isoformat() if a.completed_at else None,
                "compute_time_seconds": a.compute_time_seconds,
                "memory_used_gb": a.memory_used_gb,
                "cost_estimate": a.cost_estimate,
            }
            for a in analyses
        ],
        total=total,
        page=(skip // limit) + 1,
        per_page=limit,
        has_next=(skip + limit) < total,
        has_prev=skip > 0
    )


@router.get("/by-chat/{chat_session_id}")
async def get_analysis_by_chat_session(
    chat_session_id: int,
    db: AsyncSession = Depends(get_db)
):
    """Get analysis linked to a chat session"""
    user = await get_current_user(db)

    stmt = select(Analysis).where(
        Analysis.chat_session_id == chat_session_id,
        Analysis.user_id == user.id
    )
    result = await db.execute(stmt)
    analysis = result.scalar_one_or_none()

    if not analysis:
        return None

    return {
        "id": analysis.id,
        "analysis_id": analysis.analysis_id,
        "title": analysis.title,
        "description": analysis.description,
        "analysis_type": analysis.analysis_type,
        "status": analysis.status,
        "input_files": analysis.input_files,
        "created_at": analysis.created_at.isoformat() if analysis.created_at else None,
    }


@router.get("/{analysis_id}", response_model=AnalysisSchema)
async def get_analysis(
    analysis_id: int,
    db: AsyncSession = Depends(get_db)
):
    """Get a specific analysis by ID"""
    user = await get_current_user(db)

    stmt = select(Analysis).where(
        Analysis.id == analysis_id,
        Analysis.user_id == user.id
    )
    result = await db.execute(stmt)
    analysis = result.scalar_one_or_none()

    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis not found")

    return AnalysisSchema(
        id=analysis.id,
        title=analysis.title,
        description=analysis.description,
        analysis_type=analysis.analysis_type,
        status=analysis.status,
        input_files=analysis.input_files,
        output_files=analysis.output_files,
        results_summary=analysis.results_summary,
        created_at=analysis.created_at,
        started_at=analysis.started_at,
        completed_at=analysis.completed_at,
        compute_time_seconds=analysis.compute_time_seconds,
        memory_used_gb=analysis.memory_used_gb,
        cost_estimate=analysis.cost_estimate
    )


# ==================== UPDATE/DELETE ENDPOINTS ====================

@router.patch("/{analysis_id}/status", response_model=APIResponse)
async def update_analysis_status(
    analysis_id: int,
    status: AnalysisStatus,
    output_files: Optional[List[str]] = None,
    results_summary: Optional[dict] = None,
    compute_time_seconds: Optional[int] = None,
    memory_used_gb: Optional[str] = None,
    cost_estimate: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
):
    """
    Update analysis status and results.

    Used to track analysis progress and store results.
    """
    user = await get_current_user(db)

    stmt = select(Analysis).where(
        Analysis.id == analysis_id,
        Analysis.user_id == user.id
    )
    result = await db.execute(stmt)
    analysis = result.scalar_one_or_none()

    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis not found")

    # Update status
    analysis.status = status.value

    # Update timestamps based on status
    if status == AnalysisStatus.RUNNING and not analysis.started_at:
        analysis.started_at = datetime.utcnow()
    elif status in [AnalysisStatus.COMPLETED, AnalysisStatus.FAILED]:
        analysis.completed_at = datetime.utcnow()

    # Update optional fields
    if output_files is not None:
        analysis.output_files = output_files
    if results_summary is not None:
        analysis.results_summary = results_summary
    if compute_time_seconds is not None:
        analysis.compute_time_seconds = compute_time_seconds
    if memory_used_gb is not None:
        analysis.memory_used_gb = memory_used_gb
    if cost_estimate is not None:
        analysis.cost_estimate = cost_estimate

    return APIResponse(
        message=f"Analysis status updated to {status.value}",
        data=AnalysisSchema(
            id=analysis.id,
            title=analysis.title,
            description=analysis.description,
            analysis_type=analysis.analysis_type,
            status=analysis.status,
            input_files=analysis.input_files,
            output_files=analysis.output_files,
            results_summary=analysis.results_summary,
            created_at=analysis.created_at,
            started_at=analysis.started_at,
            completed_at=analysis.completed_at,
            compute_time_seconds=analysis.compute_time_seconds,
            memory_used_gb=analysis.memory_used_gb,
            cost_estimate=analysis.cost_estimate
        ).model_dump()
    )


@router.delete("/{analysis_id}", response_model=APIResponse)
async def delete_analysis(
    analysis_id: int,
    db: AsyncSession = Depends(get_db)
):
    """
    Delete an analysis record.

    Note: This does not delete the actual output files.
    """
    user = await get_current_user(db)

    stmt = select(Analysis).where(
        Analysis.id == analysis_id,
        Analysis.user_id == user.id
    )
    result = await db.execute(stmt)
    analysis = result.scalar_one_or_none()

    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis not found")

    await db.delete(analysis)

    return APIResponse(message="Analysis deleted successfully")


# ==================== STATISTICS ENDPOINTS ====================

@router.get("/stats/summary", response_model=APIResponse)
async def get_analysis_stats(
    db: AsyncSession = Depends(get_db)
):
    """Get analysis statistics for the current user"""
    user = await get_current_user(db)

    # Total analyses
    total_stmt = select(func.count(Analysis.id)).where(Analysis.user_id == user.id)
    total_result = await db.execute(total_stmt)
    total = total_result.scalar()

    # Completed analyses
    completed_stmt = select(func.count(Analysis.id)).where(
        Analysis.user_id == user.id,
        Analysis.status == "completed"
    )
    completed_result = await db.execute(completed_stmt)
    completed = completed_result.scalar()

    # Running analyses
    running_stmt = select(func.count(Analysis.id)).where(
        Analysis.user_id == user.id,
        Analysis.status == "running"
    )
    running_result = await db.execute(running_stmt)
    running = running_result.scalar()

    # Failed analyses
    failed_stmt = select(func.count(Analysis.id)).where(
        Analysis.user_id == user.id,
        Analysis.status == "failed"
    )
    failed_result = await db.execute(failed_stmt)
    failed = failed_result.scalar()

    # Total compute time
    compute_stmt = select(func.sum(Analysis.compute_time_seconds)).where(
        Analysis.user_id == user.id,
        Analysis.compute_time_seconds.isnot(None)
    )
    compute_result = await db.execute(compute_stmt)
    total_compute_seconds = compute_result.scalar() or 0

    return APIResponse(
        message="Analysis statistics",
        data=AnalysisStats(
            total_analyses=total,
            completed_analyses=completed,
            running_analyses=running,
            failed_analyses=failed,
            total_compute_hours=total_compute_seconds / 3600
        ).model_dump()
    )


@router.get("/types/available", response_model=List[str])
async def get_available_analysis_types():
    """Get list of available analysis types"""
    return [t.value for t in AnalysisType]
