"""
Settings router - handles user preferences and configuration

Provides endpoints for:
- Getting/setting storage preferences
- Validating custom paths
- Getting folder structure previews
"""

import os
from typing import Optional, Dict, Any
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from models.database import get_db, User, get_or_create_user
from services.storage_config import (
    StorageConfigService,
    StoragePreferences,
    StorageLocationType,
    storage_config_service,
)


router = APIRouter(prefix="/settings")


# ==================== SCHEMAS ====================

class StoragePreferencesRequest(BaseModel):
    """Request schema for updating storage preferences."""
    location_type: StorageLocationType = Field(
        default="downloads",
        description="Where to save output files: downloads, workspace, or custom"
    )
    custom_path: Optional[str] = Field(
        default=None,
        description="Custom path when location_type is 'custom'"
    )
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
    location_type: str
    custom_path: Optional[str]
    create_subfolders: bool
    subfolder_by_date: bool
    subfolder_by_type: bool
    base_path: str
    downloads_folder: str
    workspace_folder: str


class FolderStructurePreview(BaseModel):
    """Preview of folder structure."""
    base_path: str
    location_type: str
    subfolders: list
    example_path: str


class PathValidationResult(BaseModel):
    """Result of path validation."""
    valid: bool
    path: str
    exists: bool
    writable: bool
    issues: list


class AllPreferencesResponse(BaseModel):
    """All user preferences."""
    storage: StoragePreferencesResponse
    # Add other preference categories here as needed


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

    Returns the configured storage location and folder organization settings.
    """
    prefs = get_storage_preferences_from_user(user)

    return StoragePreferencesResponse(
        location_type=prefs.location_type,
        custom_path=prefs.custom_path,
        create_subfolders=prefs.create_subfolders,
        subfolder_by_date=prefs.subfolder_by_date,
        subfolder_by_type=prefs.subfolder_by_type,
        base_path=str(storage_config_service.get_base_output_path(prefs, user.id)),
        downloads_folder=str(storage_config_service.get_system_downloads_folder()),
        workspace_folder=str(storage_config_service._workspace_dir),
    )


@router.put("/storage", response_model=StoragePreferencesResponse)
async def update_storage_preferences(
    request: StoragePreferencesRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """
    Update storage preferences for the user.

    Validates custom paths before saving.
    """
    # Validate custom path if specified
    if request.location_type == "custom":
        if not request.custom_path:
            raise HTTPException(
                status_code=400,
                detail="custom_path is required when location_type is 'custom'"
            )
        validation = storage_config_service.validate_custom_path(request.custom_path)
        if not validation["valid"]:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid custom path: {', '.join(validation['issues'])}"
            )

    # Update user preferences
    prefs = StoragePreferences(
        location_type=request.location_type,
        custom_path=request.custom_path,
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
        location_type=prefs.location_type,
        custom_path=prefs.custom_path,
        create_subfolders=prefs.create_subfolders,
        subfolder_by_date=prefs.subfolder_by_date,
        subfolder_by_type=prefs.subfolder_by_type,
        base_path=str(storage_config_service.get_base_output_path(prefs, user.id)),
        downloads_folder=str(storage_config_service.get_system_downloads_folder()),
        workspace_folder=str(storage_config_service._workspace_dir),
    )


@router.get("/storage/preview", response_model=FolderStructurePreview)
async def preview_folder_structure(
    location_type: StorageLocationType = "downloads",
    custom_path: Optional[str] = None,
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
        location_type=location_type,
        custom_path=custom_path,
        create_subfolders=create_subfolders,
        subfolder_by_date=subfolder_by_date,
        subfolder_by_type=subfolder_by_type,
    )

    preview = storage_config_service.get_folder_structure_preview(prefs, user.id)

    return FolderStructurePreview(**preview)


@router.post("/storage/validate-path", response_model=PathValidationResult)
async def validate_custom_path(
    path: str,
):
    """
    Validate a custom path for use as output directory.

    Checks if the path is valid, exists, and is writable.
    """
    result = storage_config_service.validate_custom_path(path)
    return PathValidationResult(**result)


@router.get("/storage/system-paths")
async def get_system_paths():
    """
    Get system default paths for reference.

    Returns the detected downloads folder and workspace directory.
    """
    return {
        "downloads_folder": str(storage_config_service.get_system_downloads_folder()),
        "workspace_folder": str(storage_config_service._workspace_dir),
        "platform": os.name,
    }


@router.get("/", response_model=AllPreferencesResponse)
async def get_all_preferences(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """
    Get all user preferences.

    Returns storage and other preference categories.
    """
    storage_prefs = get_storage_preferences_from_user(user)

    storage_response = StoragePreferencesResponse(
        location_type=storage_prefs.location_type,
        custom_path=storage_prefs.custom_path,
        create_subfolders=storage_prefs.create_subfolders,
        subfolder_by_date=storage_prefs.subfolder_by_date,
        subfolder_by_type=storage_prefs.subfolder_by_type,
        base_path=str(storage_config_service.get_base_output_path(storage_prefs, user.id)),
        downloads_folder=str(storage_config_service.get_system_downloads_folder()),
        workspace_folder=str(storage_config_service._workspace_dir),
    )

    return AllPreferencesResponse(
        storage=storage_response,
    )
