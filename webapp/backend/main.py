"""
BioAgent Web API - Main FastAPI Application
Enhanced with security measures and production-ready configuration
"""

import os
import sys
from pathlib import Path
from contextlib import asynccontextmanager
from typing import List

# Load environment variables from .env file
from dotenv import load_dotenv

# Load from current directory .env, then from bioagent root as fallback
env_path = Path(__file__).parent / ".env"
if env_path.exists():
    load_dotenv(env_path)
else:
    # Fallback to bioagent root .env
    root_env = Path(__file__).parent.parent.parent / ".env"
    if root_env.exists():
        load_dotenv(root_env)

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
import uvicorn

# Add bioagent root to path for imports
BIOAGENT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(BIOAGENT_ROOT))

from routers import chat, files, analyses
from models.database import init_db
from middleware.security import (
    SecurityHeadersMiddleware,
    RateLimitMiddleware,
    validate_api_key,
)
from middleware.logging import RequestLoggingMiddleware


# Consolidated workspace directory (all outputs in one place)
def _get_workspace_dir() -> Path:
    """Get workspace directory, platform-aware."""
    if sys.platform == "win32":
        default = Path.home() / "bioagent_workspace"
    else:
        default = Path("/workspace")
    return Path(os.getenv("BIOAGENT_WORKSPACE", str(default)))

WORKSPACE_DIR = _get_workspace_dir()
UPLOAD_DIR = WORKSPACE_DIR / "uploads"


# Configuration from environment
class Config:
    """Application configuration from environment variables"""
    DEBUG = os.getenv("ENVIRONMENT", "development") == "development"
    ALLOWED_ORIGINS: List[str] = os.getenv(
        "ALLOWED_ORIGINS",
        "http://localhost:3000,http://127.0.0.1:3000,http://localhost:8001,http://127.0.0.1:8001"
    ).split(",")
    API_KEY_REQUIRED = os.getenv("API_KEY_REQUIRED", "false").lower() == "true"
    RATE_LIMIT_PER_MINUTE = int(os.getenv("RATE_LIMIT_PER_MINUTE", "60"))
    MAX_UPLOAD_SIZE_MB = int(os.getenv("MAX_UPLOAD_SIZE_MB", "500"))


config = Config()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler for startup and shutdown"""
    # Startup
    print("Starting BioAgent Web API...")
    await init_db()
    print("Database initialized")

    # Create required directories (consolidated in workspace)
    WORKSPACE_DIR.mkdir(parents=True, exist_ok=True)
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    os.makedirs("logs", exist_ok=True)
    print(f"📁 Workspace: {WORKSPACE_DIR}")
    print(f"📁 Uploads: {UPLOAD_DIR}")

    # Initialize agent service and show mode
    try:
        from services.agent_service import bioagent_service
        if bioagent_service.config:
            if bioagent_service.config.fast_mode:
                print("⚡ FAST MODE enabled - single agent, no memory overhead")
            else:
                print("🔬 FULL MODE - multi-agent with memory system")

                # Preload embedding model only in full mode
                if bioagent_service.agent and bioagent_service.agent.memory:
                    print("Preloading embedding model (this may take a few seconds)...")
                    # Trigger lazy initialization of vector store and embedding model
                    vs = bioagent_service.agent.memory.vector_store
                    if vs and hasattr(vs, '_ensure_initialized'):
                        vs._ensure_initialized()
                    # Do a dummy search to fully warm up the model
                    if vs and hasattr(vs, 'search'):
                        vs.search("warmup query", max_results=1)
                    print("✅ Embedding model preloaded and ready")
    except Exception as e:
        print(f"⚠️ Agent initialization issue: {e}")

    yield

    # Shutdown
    print("Shutting down BioAgent Web API...")


# Create FastAPI application
app = FastAPI(
    title="BioAgent Web API",
    description="""
    Expert bioinformatics AI agent with computational capabilities.

    ## Features
    - 72+ specialized bioinformatics tools
    - Real-time streaming responses via SSE
    - File upload and management for genomic data
    - Multi-agent architecture for complex analyses

    ## Security
    - Rate limiting enabled
    - CORS protection
    - Request validation
    - Secure headers
    """,
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs" if config.DEBUG else None,  # Disable docs in production
    redoc_url="/redoc" if config.DEBUG else None,
)


# ==================== MIDDLEWARE (order matters - last added = first executed) ====================

# CORS - configure allowed origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["Content-Disposition"],
    max_age=600,  # Cache preflight requests for 10 minutes
)

# Gzip compression for responses
app.add_middleware(GZipMiddleware, minimum_size=1000)

# Security headers
app.add_middleware(SecurityHeadersMiddleware)

# Rate limiting
app.add_middleware(
    RateLimitMiddleware,
    requests_per_minute=config.RATE_LIMIT_PER_MINUTE,
)

# Request logging
app.add_middleware(RequestLoggingMiddleware)


# ==================== EXCEPTION HANDLERS ====================

@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Custom HTTP exception handler"""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "error": exc.detail,
            "status_code": exc.status_code,
        },
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Catch-all exception handler - don't expose internal errors"""
    # Log the actual error for debugging
    import traceback
    print(f"Unhandled exception: {traceback.format_exc()}")

    # Return generic error to client
    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "error": "An internal error occurred. Please try again later.",
            "status_code": 500,
        },
    )


# ==================== STATIC FILES ====================

# Mount uploads directory (inside workspace) with validation
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=str(UPLOAD_DIR)), name="uploads")


# ==================== ROUTERS ====================

app.include_router(chat.router, prefix="/api", tags=["chat"])
app.include_router(files.router, prefix="/api", tags=["files"])
app.include_router(analyses.router, prefix="/api", tags=["analyses"])


# ==================== ROOT ENDPOINTS ====================

@app.get("/")
async def root():
    """Root endpoint - basic API info"""
    return {
        "message": "BioAgent Web API",
        "version": "1.0.0",
        "docs": "/docs" if config.DEBUG else "Disabled in production",
        "health": "/health",
    }


@app.get("/health")
async def health_check():
    """Health check endpoint for monitoring"""
    return {
        "status": "healthy",
        "service": "bioagent-api",
        "version": "1.0.0",
    }


@app.get("/api/info")
async def api_info():
    """API information endpoint"""
    return {
        "name": "BioAgent Web API",
        "version": "1.0.0",
        "tools_available": 72,
        "specialists": [
            "pipeline_engineer",
            "statistician",
            "literature_agent",
            "qc_reviewer",
            "domain_expert",
            "research_agent",
        ],
        "capabilities": [
            "database_queries",
            "code_execution",
            "file_ingestion",
            "visualization",
            "ml_prediction",
            "cloud_execution",
            "literature_search",
        ],
    }


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8001,
        reload=config.DEBUG,
        log_level="info" if config.DEBUG else "warning",
        access_log=config.DEBUG,
    )
