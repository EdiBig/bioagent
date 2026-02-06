"""
Pydantic schemas for BioAgent Web API

Defines request/response models with validation.
"""

from pydantic import BaseModel, Field, EmailStr, field_validator
from typing import List, Optional, Dict, Any
from datetime import datetime
from enum import Enum
import re


# ==================== ENUMS ====================

class MessageRole(str, Enum):
    """Valid message roles"""
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


class AnalysisStatus(str, Enum):
    """Valid analysis statuses"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class AnalysisType(str, Enum):
    """Available analysis types"""
    RNASEQ = "rnaseq"
    DIFFERENTIAL_EXPRESSION = "differential_expression"
    PATHWAY_ENRICHMENT = "pathway_enrichment"
    VARIANT_CALLING = "variant_calling"
    VARIANT_ANNOTATION = "variant_annotation"
    SINGLE_CELL = "single_cell"
    PROTEIN_STRUCTURE = "protein_structure"
    LITERATURE_SEARCH = "literature_search"
    CUSTOM = "custom"


# ==================== CHAT SCHEMAS ====================

class ChatMessageCreate(BaseModel):
    """Request schema for creating a new message"""
    content: str = Field(
        ...,
        min_length=1,
        max_length=100000,
        description="Message content"
    )
    attached_files: List[str] = Field(
        default=[],
        max_length=10,
        description="List of attached file paths"
    )

    @field_validator("content")
    @classmethod
    def validate_content(cls, v: str) -> str:
        """Validate and sanitize content"""
        # Remove null bytes
        v = v.replace("\x00", "")
        # Trim whitespace
        v = v.strip()
        if not v:
            raise ValueError("Content cannot be empty")
        return v


class ChatMessage(BaseModel):
    """Response schema for a chat message"""
    id: int
    role: MessageRole
    content: str
    created_at: datetime
    token_count: int = 0
    tool_calls: List[Dict[str, Any]] = []
    tool_results: List[Dict[str, Any]] = []
    attached_files: List[str] = []

    class Config:
        from_attributes = True


class ChatSessionCreate(BaseModel):
    """Request schema for creating a chat session"""
    title: str = Field(
        default="New Chat",
        min_length=1,
        max_length=255,
        description="Session title"
    )


class ChatSession(BaseModel):
    """Response schema for a chat session with messages"""
    id: int
    title: str
    created_at: datetime
    updated_at: datetime
    model_used: str
    total_tokens: int = 0
    total_cost: str = "0.00"
    messages: List[ChatMessage] = []

    class Config:
        from_attributes = True


class ChatSessionSummary(BaseModel):
    """Lightweight session info for listing"""
    id: int
    title: str
    created_at: datetime
    updated_at: datetime
    message_count: int = 0
    total_tokens: int = 0

    class Config:
        from_attributes = True


# ==================== FILE SCHEMAS ====================

class FileUpload(BaseModel):
    """Response schema for file upload"""
    filename: str
    size: int
    content_type: str
    file_path: str
    uploaded_at: datetime = Field(default_factory=datetime.utcnow)


class FileInfo(BaseModel):
    """Response schema for file information"""
    filename: str
    size: int
    content_type: str
    url: str
    uploaded_at: datetime


# ==================== ANALYSIS SCHEMAS ====================

class AnalysisCreate(BaseModel):
    """Request schema for creating an analysis"""
    title: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = Field(None, max_length=5000)
    analysis_type: AnalysisType
    input_files: List[str] = Field(default=[], max_length=100)


class Analysis(BaseModel):
    """Response schema for an analysis"""
    id: int
    title: str
    description: Optional[str] = None
    analysis_type: str
    status: AnalysisStatus
    input_files: List[str] = []
    output_files: List[str] = []
    results_summary: Dict[str, Any] = {}
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    compute_time_seconds: Optional[int] = None
    memory_used_gb: Optional[str] = None
    cost_estimate: Optional[str] = None

    class Config:
        from_attributes = True


class AnalysisStats(BaseModel):
    """Statistics about user's analyses"""
    total_analyses: int
    completed_analyses: int
    running_analyses: int
    failed_analyses: int
    total_compute_hours: float


# ==================== USER SCHEMAS ====================

class UserCreate(BaseModel):
    """Request schema for creating a user"""
    email: EmailStr
    clerk_user_id: Optional[str] = None
    full_name: Optional[str] = Field(None, max_length=255)


class User(BaseModel):
    """Response schema for a user"""
    id: int
    clerk_user_id: Optional[str]
    email: str
    full_name: Optional[str]
    created_at: datetime
    preferences: Dict[str, Any] = {}

    class Config:
        from_attributes = True


class UserPreferencesUpdate(BaseModel):
    """Request schema for updating user preferences"""
    preferences: Dict[str, Any] = Field(default_factory=dict)


# ==================== API RESPONSE WRAPPERS ====================

class APIResponse(BaseModel):
    """Generic API response wrapper"""
    success: bool = True
    message: str = "Success"
    data: Optional[Any] = None
    error: Optional[str] = None


class PaginatedResponse(BaseModel):
    """Paginated response wrapper"""
    items: List[Any]
    total: int
    page: int = 1
    per_page: int = 20
    has_next: bool = False
    has_prev: bool = False


# ==================== STREAMING SCHEMAS ====================

class StreamEvent(BaseModel):
    """Base streaming event schema"""
    event: str
    data: Dict[str, Any]
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class ThinkingEvent(StreamEvent):
    """Agent thinking event"""
    event: str = "thinking"


class ToolStartEvent(StreamEvent):
    """Tool execution started"""
    event: str = "tool_start"


class ToolResultEvent(StreamEvent):
    """Tool execution completed"""
    event: str = "tool_result"


class CodeOutputEvent(StreamEvent):
    """Code execution output"""
    event: str = "code_output"


class TextDeltaEvent(StreamEvent):
    """Text response chunk"""
    event: str = "text_delta"


class ErrorEvent(StreamEvent):
    """Error event"""
    event: str = "error"


class DoneEvent(StreamEvent):
    """Processing complete"""
    event: str = "done"
