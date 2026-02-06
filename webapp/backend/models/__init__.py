"""
Database models for BioAgent Web API
"""

from .database import (
    Base,
    User,
    ChatSession,
    Message,
    Analysis,
    init_db,
    get_db,
    async_session,
)
from .schemas import (
    MessageRole,
    AnalysisStatus,
    ChatMessageCreate,
    ChatMessage,
    ChatSessionCreate,
    ChatSession as ChatSessionSchema,
    ChatSessionSummary,
    FileUpload,
    FileInfo,
    AnalysisCreate,
    Analysis as AnalysisSchema,
    UserCreate,
    User as UserSchema,
    APIResponse,
    PaginatedResponse,
)

__all__ = [
    # Database
    "Base",
    "User",
    "ChatSession",
    "Message",
    "Analysis",
    "init_db",
    "get_db",
    "async_session",
    # Schemas
    "MessageRole",
    "AnalysisStatus",
    "ChatMessageCreate",
    "ChatMessage",
    "ChatSessionCreate",
    "ChatSessionSchema",
    "ChatSessionSummary",
    "FileUpload",
    "FileInfo",
    "AnalysisCreate",
    "AnalysisSchema",
    "UserCreate",
    "UserSchema",
    "APIResponse",
    "PaginatedResponse",
]
