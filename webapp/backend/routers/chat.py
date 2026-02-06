"""
Chat router - handles chat sessions, messaging, and streaming

Provides endpoints for:
- Creating and managing chat sessions
- Sending messages with streaming responses
- Retrieving chat history
"""

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from typing import List

from models.database import get_db, ChatSession, Message, User, Analysis, get_or_create_user
from models.schemas import (
    ChatSessionCreate, ChatSession as ChatSessionSchema,
    ChatSessionSummary, ChatMessageCreate, ChatMessage as ChatMessageSchema,
    APIResponse
)
from services.streaming import streaming_service


router = APIRouter(prefix="/chat")


# ==================== HELPER FUNCTIONS ====================

async def get_current_user(db: AsyncSession) -> User:
    """
    Get current user from authentication.

    TODO: Integrate with Clerk authentication.
    For now, creates/returns a default user.
    """
    return await get_or_create_user(
        db,
        email="demo@bioagent.ai",
        full_name="Demo User"
    )


# ==================== SESSION MANAGEMENT ====================

@router.post("/sessions", response_model=APIResponse)
async def create_chat_session(
    session_data: ChatSessionCreate,
    db: AsyncSession = Depends(get_db)
):
    """
    Create a new chat session with auto-generated BIO-style ID.

    Returns the session ID and title for the new chat.
    """
    from datetime import datetime

    user = await get_current_user(db)

    # Generate BIO-style title: CHAT-YYYYMMDD-NNN
    today = datetime.utcnow().strftime("%Y%m%d")

    # Count existing sessions today to get sequence number
    from sqlalchemy import func
    count_stmt = select(func.count(ChatSession.id)).where(
        ChatSession.user_id == user.id,
        ChatSession.title.like(f"CHAT-{today}-%")
    )
    result = await db.execute(count_stmt)
    count = result.scalar() or 0

    # Generate title
    sequence = str(count + 1).zfill(3)
    auto_title = f"CHAT-{today}-{sequence}"

    # Use provided title if not "New Chat", otherwise use auto-generated
    title = session_data.title if session_data.title and session_data.title != "New Chat" else auto_title

    new_session = ChatSession(
        user_id=user.id,
        title=title
    )

    db.add(new_session)
    await db.flush()
    await db.refresh(new_session)

    return APIResponse(
        message="Chat session created successfully",
        data={"session_id": new_session.id, "title": new_session.title}
    )


@router.get("/sessions", response_model=List[ChatSessionSummary])
async def list_chat_sessions(
    skip: int = 0,
    limit: int = 20,
    db: AsyncSession = Depends(get_db)
):
    """
    List user's chat sessions.

    Returns sessions ordered by last update, with message counts.
    """
    user = await get_current_user(db)

    # Get sessions with message count
    stmt = (
        select(
            ChatSession,
            func.count(Message.id).label("message_count")
        )
        .outerjoin(Message)
        .where(ChatSession.user_id == user.id)
        .group_by(ChatSession.id)
        .order_by(ChatSession.updated_at.desc())
        .offset(skip)
        .limit(limit)
    )

    result = await db.execute(stmt)
    sessions_with_counts = result.all()

    return [
        ChatSessionSummary(
            id=session.id,
            title=session.title,
            created_at=session.created_at,
            updated_at=session.updated_at,
            message_count=message_count,
            total_tokens=session.total_tokens
        )
        for session, message_count in sessions_with_counts
    ]


@router.get("/sessions/{session_id}", response_model=ChatSessionSchema)
async def get_chat_session(
    session_id: int,
    db: AsyncSession = Depends(get_db)
):
    """
    Get a specific chat session with all messages.

    Returns the full session including message history.
    """
    user = await get_current_user(db)

    # Get session
    stmt = select(ChatSession).where(
        ChatSession.id == session_id,
        ChatSession.user_id == user.id
    )
    result = await db.execute(stmt)
    session = result.scalar_one_or_none()

    if not session:
        raise HTTPException(status_code=404, detail="Chat session not found")

    # Get messages
    messages_stmt = (
        select(Message)
        .where(Message.chat_session_id == session_id)
        .order_by(Message.created_at.asc())
    )
    messages_result = await db.execute(messages_stmt)
    messages = messages_result.scalars().all()

    return ChatSessionSchema(
        id=session.id,
        title=session.title,
        created_at=session.created_at,
        updated_at=session.updated_at,
        model_used=session.model_used,
        total_tokens=session.total_tokens,
        total_cost=session.total_cost,
        messages=[
            ChatMessageSchema(
                id=msg.id,
                role=msg.role,
                content=msg.content,
                created_at=msg.created_at,
                token_count=msg.token_count,
                tool_calls=msg.tool_calls,
                tool_results=msg.tool_results,
                attached_files=msg.attached_files
            ) for msg in messages
        ]
    )


@router.patch("/sessions/{session_id}", response_model=APIResponse)
async def update_chat_session(
    session_id: int,
    session_data: ChatSessionCreate,
    db: AsyncSession = Depends(get_db)
):
    """Update a chat session's title"""
    user = await get_current_user(db)

    stmt = select(ChatSession).where(
        ChatSession.id == session_id,
        ChatSession.user_id == user.id
    )
    result = await db.execute(stmt)
    session = result.scalar_one_or_none()

    if not session:
        raise HTTPException(status_code=404, detail="Chat session not found")

    session.title = session_data.title

    return APIResponse(
        message="Chat session updated successfully",
        data={"session_id": session.id, "title": session.title}
    )


@router.delete("/sessions/{session_id}", response_model=APIResponse)
async def delete_chat_session(
    session_id: int,
    db: AsyncSession = Depends(get_db)
):
    """
    Delete a chat session and all its messages.

    This is a permanent deletion.
    """
    user = await get_current_user(db)

    stmt = select(ChatSession).where(
        ChatSession.id == session_id,
        ChatSession.user_id == user.id
    )
    result = await db.execute(stmt)
    session = result.scalar_one_or_none()

    if not session:
        raise HTTPException(status_code=404, detail="Chat session not found")

    await db.delete(session)

    return APIResponse(message="Chat session deleted successfully")


# ==================== MESSAGING ====================

@router.post("/sessions/{session_id}/messages")
async def send_message_stream(
    session_id: int,
    message_data: ChatMessageCreate,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db)
):
    """
    Send a message and get streamed response via SSE.

    Returns a streaming response with real-time updates:
    - thinking: Agent reasoning
    - tool_start: Tool execution started
    - tool_result: Tool execution completed
    - text_delta: Response text chunks
    - done: Processing complete
    """
    user = await get_current_user(db)

    # Verify session exists and belongs to user
    stmt = select(ChatSession).where(
        ChatSession.id == session_id,
        ChatSession.user_id == user.id
    )
    result = await db.execute(stmt)
    session = result.scalar_one_or_none()

    if not session:
        raise HTTPException(status_code=404, detail="Chat session not found")

    # Auto-update title if this is the first message and title is auto-generated
    if session.title.startswith("CHAT-"):
        # Check if this is the first message
        msg_count_stmt = select(func.count(Message.id)).where(
            Message.chat_session_id == session_id
        )
        msg_count_result = await db.execute(msg_count_stmt)
        msg_count = msg_count_result.scalar() or 0

        if msg_count == 0:
            # Generate title from first message (first 50 chars, cleaned)
            import re
            clean_content = re.sub(r'[^\w\s]', '', message_data.content)
            words = clean_content.split()[:6]  # First 6 words
            summary = ' '.join(words)
            if len(summary) > 40:
                summary = summary[:40].rsplit(' ', 1)[0]
            if summary:
                session.title = summary.title()

    # Check if this chat session has a linked analysis with files
    analysis_context = None
    analysis_stmt = select(Analysis).where(
        Analysis.chat_session_id == session_id,
        Analysis.user_id == user.id
    )
    analysis_result = await db.execute(analysis_stmt)
    linked_analysis = analysis_result.scalar_one_or_none()

    if linked_analysis and linked_analysis.input_files:
        analysis_context = {
            "analysis_id": linked_analysis.analysis_id,
            "title": linked_analysis.title,
            "analysis_type": linked_analysis.analysis_type,
            "input_files": linked_analysis.input_files,
        }

    # Save user message to database
    user_message = Message(
        chat_session_id=session_id,
        role="user",
        content=message_data.content,
        attached_files=message_data.attached_files
    )
    db.add(user_message)
    await db.flush()

    # Create streaming response
    async def message_generator():
        full_response = []
        tool_calls = []
        tool_results = []

        async for event in streaming_service.stream_agent_response(
            message=message_data.content,
            chat_session_id=session_id,
            user_id=user.id,
            attached_files=message_data.attached_files,
            analysis_context=analysis_context
        ):
            # Collect response parts
            if event.event == "text_delta":
                full_response.append(event.data.get("delta", ""))
            elif event.event == "tool_start":
                tool_calls.append(event.data)
            elif event.event == "tool_result":
                tool_results.append(event.data)

            yield event

        # After streaming completes, save assistant message in background
        background_tasks.add_task(
            save_assistant_response,
            session_id,
            "".join(full_response),
            tool_calls,
            tool_results,
            0  # Token count (would come from agent)
        )

    return await streaming_service.create_sse_response(message_generator())


@router.get("/sessions/{session_id}/messages", response_model=List[ChatMessageSchema])
async def get_session_messages(
    session_id: int,
    skip: int = 0,
    limit: int = 50,
    db: AsyncSession = Depends(get_db)
):
    """
    Get messages from a chat session.

    Returns messages in chronological order with pagination.
    """
    user = await get_current_user(db)

    # Verify session ownership
    session_stmt = select(ChatSession).where(
        ChatSession.id == session_id,
        ChatSession.user_id == user.id
    )
    session_result = await db.execute(session_stmt)
    session = session_result.scalar_one_or_none()

    if not session:
        raise HTTPException(status_code=404, detail="Chat session not found")

    # Get messages
    messages_stmt = (
        select(Message)
        .where(Message.chat_session_id == session_id)
        .order_by(Message.created_at.asc())
        .offset(skip)
        .limit(limit)
    )
    result = await db.execute(messages_stmt)
    messages = result.scalars().all()

    return [
        ChatMessageSchema(
            id=msg.id,
            role=msg.role,
            content=msg.content,
            created_at=msg.created_at,
            token_count=msg.token_count,
            tool_calls=msg.tool_calls,
            tool_results=msg.tool_results,
            attached_files=msg.attached_files
        ) for msg in messages
    ]


# ==================== BACKGROUND TASKS ====================

async def save_assistant_response(
    session_id: int,
    content: str,
    tool_calls: list = None,
    tool_results: list = None,
    token_count: int = 0
):
    """
    Background task to save assistant response to database.

    Called after streaming completes.
    """
    from models.database import async_session

    async with async_session() as db:
        assistant_message = Message(
            chat_session_id=session_id,
            role="assistant",
            content=content,
            tool_calls=tool_calls or [],
            tool_results=tool_results or [],
            token_count=token_count
        )
        db.add(assistant_message)

        # Update session token count
        session_stmt = select(ChatSession).where(ChatSession.id == session_id)
        session_result = await db.execute(session_stmt)
        session = session_result.scalar_one_or_none()

        if session:
            session.total_tokens += token_count

        await db.commit()
