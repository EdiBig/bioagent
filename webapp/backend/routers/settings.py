"""
Settings router - handles user preferences and configuration

Provides endpoints for:
- Getting/setting storage organization preferences
- Getting storage info and folder structure previews
"""

from typing import Dict, Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from models.database import get_db, User, get_or_create_user
from services.storage_config import (
    StorageConfigService,
    StoragePreferences,
    storage_config_service,
)


router = APIRouter(prefix="/settings")


# ==================== SCHEMAS ====================

class StoragePreferencesRequest(BaseModel):
    """Request schema for updating storage preferences."""
    create_subfolders: bool = Field(
        default=True,
        description="Automatically create organized subfolders"
    )
    subfolder_by_date: bool = Field(
        default=True,
        description="Organize files by date (YYYY-MM-DD)"
    )
    subfolder_by_type: bool = Field(
        default=True,
        description="Organize files by type (results, reports, figures, etc.)"
    )


class StoragePreferencesResponse(BaseModel):
    """Response schema for storage preferences."""
    create_subfolders: bool
    subfolder_by_date: bool
    subfolder_by_type: bool
    workspace_path: str
    outputs_path: str
    uploads_path: str


class FolderStructurePreview(BaseModel):
    """Preview of folder structure."""
    workspace_path: str
    base_path: str
    subfolders: list
    example_path: str


class StorageInfoResponse(BaseModel):
    """Storage system information."""
    workspace: str
    uploads: str
    outputs: str
    projects: str
    exists: bool
    structure: Dict[str, str]


# ==================== HELPER FUNCTIONS ====================

async def get_current_user(db: AsyncSession = Depends(get_db)) -> User:
    """Get current user from authentication."""
    return await get_or_create_user(
        db,
        email="demo@bioagent.ai",
        full_name="Demo User"
    )


def get_storage_preferences_from_user(user: User) -> StoragePreferences:
    """Extract storage preferences from user's preferences JSON."""
    prefs = user.preferences or {}
    storage_prefs = prefs.get("storage", {})
    return StoragePreferences.from_dict(storage_prefs)


# ==================== ENDPOINTS ====================

@router.get("/storage", response_model=StoragePreferencesResponse)
async def get_storage_preferences(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """
    Get current storage preferences for the user.

    All files are stored in a single consolidated workspace directory.
    These settings control how files are organized within that workspace.
    """
    prefs = get_storage_preferences_from_user(user)

    return StoragePreferencesResponse(
        create_subfolders=prefs.create_subfolders,
        subfolder_by_date=prefs.subfolder_by_date,
        subfolder_by_type=prefs.subfolder_by_type,
        workspace_path=str(storage_config_service.workspace_dir),
        outputs_path=str(storage_config_service.outputs_dir),
        uploads_path=str(storage_config_service.uploads_dir),
    )


@router.put("/storage", response_model=StoragePreferencesResponse)
async def update_storage_preferences(
    request: StoragePreferencesRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """
    Update storage organization preferences for the user.

    Controls how files are organized within the workspace directory.
    """
    # Update user preferences
    prefs = StoragePreferences(
        create_subfolders=request.create_subfolders,
        subfolder_by_date=request.subfolder_by_date,
        subfolder_by_type=request.subfolder_by_type,
    )

    # Merge into user's preferences JSON
    user_prefs = user.preferences or {}
    user_prefs["storage"] = prefs.to_dict()
    user.preferences = user_prefs

    await db.commit()
    await db.refresh(user)

    return StoragePreferencesResponse(
        create_subfolders=prefs.create_subfolders,
        subfolder_by_date=prefs.subfolder_by_date,
        subfolder_by_type=prefs.subfolder_by_type,
        workspace_path=str(storage_config_service.workspace_dir),
        outputs_path=str(storage_config_service.outputs_dir),
        uploads_path=str(storage_config_service.uploads_dir),
    )


@router.get("/storage/preview", response_model=FolderStructurePreview)
async def preview_folder_structure(
    create_subfolders: bool = True,
    subfolder_by_date: bool = True,
    subfolder_by_type: bool = True,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """
    Preview the folder structure that will be created.

    Useful for showing users what the output organization will look like
    before they save their preferences.
    """
    prefs = StoragePreferences(
        create_subfolders=create_subfolders,
        subfolder_by_date=subfolder_by_date,
        subfolder_by_type=subfolder_by_type,
    )

    preview = storage_config_service.get_folder_structure_preview(prefs, user.id)

    return FolderStructurePreview(**preview)


@router.get("/storage/info", response_model=StorageInfoResponse)
async def get_storage_info():
    """
    Get information about the storage system.

    Returns paths and structure of the consolidated workspace.
    """
    info = storage_config_service.get_storage_info()
    return StorageInfoResponse(**info)


@router.post("/storage/ensure-structure")
async def ensure_workspace_structure():
    """
    Ensure the complete workspace structure exists.

    Creates all necessary directories if they don't exist.
    """
    dirs = storage_config_service.ensure_workspace_structure()
    return {
        "success": True,
        "message": "Workspace structure ensured",
        "directories": {name: str(path) for name, path in dirs.items()}
    }
