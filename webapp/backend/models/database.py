"""
Database models for BioAgent Web API

Uses SQLAlchemy with async support and PostgreSQL.
Includes models for users, chat sessions, messages, and analyses.
"""

import os
from datetime import datetime
from typing import Optional

from sqlalchemy import (
    Column, Integer, String, DateTime, Text, Boolean,
    ForeignKey, JSON, Index, event, text
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy.ext.asyncio import (
    create_async_engine,
    AsyncSession,
    async_sessionmaker
)

Base = declarative_base()


# ==================== DATABASE CONFIGURATION ====================

def get_database_url() -> str:
    """
    Get database URL from environment with secure defaults.

    Supports:
    - DATABASE_URL: Full connection string
    - Individual components: DB_HOST, DB_PORT, DB_USER, DB_PASSWORD, DB_NAME
    - SQLite for development (default when no PostgreSQL configured)
    """
    # Check for full URL first
    database_url = os.getenv("DATABASE_URL")
    if database_url:
        # Ensure async driver for PostgreSQL
        if database_url.startswith("postgresql://"):
            database_url = database_url.replace(
                "postgresql://", "postgresql+asyncpg://", 1
            )
        return database_url

    # Check if PostgreSQL host is configured
    host = os.getenv("DB_HOST")
    if host:
        port = os.getenv("DB_PORT", "5432")
        user = os.getenv("DB_USER", "bioagent")
        password = os.getenv("DB_PASSWORD", "bioagent_password")
        name = os.getenv("DB_NAME", "bioagent")
        return f"postgresql+asyncpg://{user}:{password}@{host}:{port}/{name}"

    # Default to SQLite for development
    db_path = os.path.join(os.path.dirname(__file__), "..", "bioagent.db")
    return f"sqlite+aiosqlite:///{db_path}"


DATABASE_URL = get_database_url()

# Create async engine with appropriate settings
if DATABASE_URL.startswith("sqlite"):
    # SQLite-specific settings for better concurrency
    # Use StaticPool for SQLite to share a single connection safely
    from sqlalchemy.pool import StaticPool
    engine = create_async_engine(
        DATABASE_URL,
        echo=os.getenv("DB_ECHO", "false").lower() == "true",
        connect_args={
            "check_same_thread": False,
            "timeout": 60,  # Wait up to 60 seconds for locks
        },
        poolclass=StaticPool,  # Use static pool for SQLite
    )
else:
    # PostgreSQL with connection pooling
    engine = create_async_engine(
        DATABASE_URL,
        echo=os.getenv("DB_ECHO", "false").lower() == "true",
        pool_size=5,
        max_overflow=10,
        pool_timeout=30,
        pool_recycle=1800,  # Recycle connections after 30 minutes
    )

# Create async session factory
async_session = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False
)


# ==================== MODELS ====================

class User(Base):
    """
    User model for authentication and user data.

    Supports Clerk authentication with fallback to local auth.
    """
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    clerk_user_id = Column(String(255), unique=True, index=True, nullable=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    full_name = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Settings (stored as encrypted JSON in production)
    api_keys = Column(JSON, default=dict)
    preferences = Column(JSON, default=dict)

    # Relationships
    chat_sessions = relationship(
        "ChatSession",
        back_populates="user",
        cascade="all, delete-orphan"
    )
    analyses = relationship(
        "Analysis",
        back_populates="user",
        cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<User {self.email}>"


class ChatSession(Base):
    """
    Chat session model for conversation history.

    Each session contains multiple messages and tracks usage.
    """
    __tablename__ = "chat_sessions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    title = Column(String(255), default="New Chat")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Session metadata
    model_used = Column(String(100), default="claude-3-sonnet")
    total_tokens = Column(Integer, default=0)
    total_cost = Column(String(20), default="0.00")

    # Relationships
    user = relationship("User", back_populates="chat_sessions")
    messages = relationship(
        "Message",
        back_populates="chat_session",
        cascade="all, delete-orphan",
        order_by="Message.created_at"
    )

    # Indexes for common queries
    __table_args__ = (
        Index("ix_chat_sessions_user_updated", "user_id", "updated_at"),
    )

    def __repr__(self):
        return f"<ChatSession {self.id}: {self.title}>"


class Message(Base):
    """
    Message model for chat history.

    Stores user messages, assistant responses, and tool execution data.
    """
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True, index=True)
    chat_session_id = Column(
        Integer,
        ForeignKey("chat_sessions.id"),
        nullable=False
    )

    # Message content
    role = Column(String(20), nullable=False)  # "user", "assistant", "system"
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Metadata
    token_count = Column(Integer, default=0)
    tool_calls = Column(JSON, default=list)
    tool_results = Column(JSON, default=list)
    attached_files = Column(JSON, default=list)

    # Relationships
    chat_session = relationship("ChatSession", back_populates="messages")

    # Indexes
    __table_args__ = (
        Index("ix_messages_session_created", "chat_session_id", "created_at"),
    )

    def __repr__(self):
        return f"<Message {self.id}: {self.role}>"


class UploadedFile(Base):
    """
    UploadedFile model for tracking user file uploads.

    Stores metadata about files and links to analyses.
    """
    __tablename__ = "uploaded_files"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    # File info
    filename = Column(String(255), nullable=False)  # Stored filename (sanitized)
    original_filename = Column(String(255), nullable=False)  # Original upload name
    file_path = Column(String(500), nullable=False)  # Full path on disk
    file_size = Column(Integer, nullable=False)  # Size in bytes
    file_type = Column(String(50), nullable=True)  # Detected format (fastq, vcf, etc.)
    content_type = Column(String(100), nullable=True)  # MIME type

    # Metadata
    description = Column(Text, nullable=True)
    checksum = Column(String(64), nullable=True)  # SHA256 hash

    # Profile data from file ingestion
    profile_data = Column(JSON, default=dict)  # Stats like read count, quality scores, etc.

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Status
    is_profiled = Column(Boolean, default=False)  # Whether file has been profiled
    is_deleted = Column(Boolean, default=False)  # Soft delete flag

    # Relationships
    user = relationship("User", backref="uploaded_files")

    # Indexes
    __table_args__ = (
        Index("ix_uploaded_files_user_type", "user_id", "file_type"),
        Index("ix_uploaded_files_user_created", "user_id", "created_at"),
    )

    def __repr__(self):
        return f"<UploadedFile {self.id}: {self.original_filename}>"


class Analysis(Base):
    """
    Analysis model for tracking bioinformatics analyses.

    Links to chat sessions and stores analysis results.
    """
    __tablename__ = "analyses"

    id = Column(Integer, primary_key=True, index=True)
    analysis_id = Column(String(50), unique=True, index=True, nullable=True)  # BIO-YYYYMMDD-NNN format
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    chat_session_id = Column(
        Integer,
        ForeignKey("chat_sessions.id"),
        nullable=True
    )

    # Analysis metadata
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    analysis_type = Column(String(50), nullable=True)
    status = Column(String(20), default="pending")  # pending, running, completed, failed

    # Files and results
    input_files = Column(JSON, default=list)
    output_files = Column(JSON, default=list)
    results_summary = Column(JSON, default=dict)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)

    # Computational details
    compute_time_seconds = Column(Integer, nullable=True)
    memory_used_gb = Column(String(20), nullable=True)
    cost_estimate = Column(String(20), nullable=True)

    # Relationships
    user = relationship("User", back_populates="analyses")

    # Indexes
    __table_args__ = (
        Index("ix_analyses_user_status", "user_id", "status"),
        Index("ix_analyses_type_status", "analysis_type", "status"),
    )

    def __repr__(self):
        return f"<Analysis {self.id}: {self.title}>"


# ==================== DATABASE INITIALIZATION ====================

async def init_db():
    """
    Initialize database tables.

    Creates all tables if they don't exist.
    In production, use Alembic migrations instead.
    """
    async with engine.begin() as conn:
        # Enable WAL mode for SQLite for better concurrency
        if DATABASE_URL.startswith("sqlite"):
            await conn.execute(text("PRAGMA journal_mode=WAL"))
            await conn.execute(text("PRAGMA synchronous=NORMAL"))
            await conn.execute(text("PRAGMA busy_timeout=30000"))
        await conn.run_sync(Base.metadata.create_all)


async def get_db():
    """
    Dependency to get database session.

    Usage:
        @router.get("/items")
        async def get_items(db: AsyncSession = Depends(get_db)):
            ...
    """
    async with async_session() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


# ==================== UTILITY FUNCTIONS ====================

async def get_or_create_user(
    db: AsyncSession,
    email: str,
    clerk_user_id: Optional[str] = None,
    full_name: Optional[str] = None
) -> User:
    """
    Get existing user or create new one.

    Args:
        db: Database session
        email: User's email
        clerk_user_id: Optional Clerk user ID
        full_name: Optional user's full name

    Returns:
        User object
    """
    from sqlalchemy import select

    # Try to find by Clerk ID first
    if clerk_user_id:
        stmt = select(User).where(User.clerk_user_id == clerk_user_id)
        result = await db.execute(stmt)
        user = result.scalar_one_or_none()
        if user:
            return user

    # Try to find by email
    stmt = select(User).where(User.email == email)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    if user:
        # Update Clerk ID if provided
        if clerk_user_id and not user.clerk_user_id:
            user.clerk_user_id = clerk_user_id
            await db.flush()
        return user

    # Create new user
    user = User(
        email=email,
        clerk_user_id=clerk_user_id,
        full_name=full_name
    )
    db.add(user)
    await db.flush()
    await db.refresh(user)

    return user
