"""
Security middleware for BioAgent Web API
Implements security headers, rate limiting, and API key validation
"""

import os
import time
import hashlib
import hmac
from collections import defaultdict
from datetime import datetime
from typing import Dict, Optional, Callable

from fastapi import HTTPException, Request, status
from fastapi.security import APIKeyHeader
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    Adds security headers to all responses.

    Headers added:
    - X-Content-Type-Options: Prevents MIME type sniffing
    - X-Frame-Options: Prevents clickjacking
    - X-XSS-Protection: Enables XSS filter
    - Strict-Transport-Security: Enforces HTTPS
    - Content-Security-Policy: Controls resource loading
    - Referrer-Policy: Controls referrer information
    - Permissions-Policy: Controls browser features
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        response = await call_next(request)

        # Prevent MIME type sniffing
        response.headers["X-Content-Type-Options"] = "nosniff"

        # Prevent clickjacking
        response.headers["X-Frame-Options"] = "DENY"

        # XSS protection (legacy but still useful)
        response.headers["X-XSS-Protection"] = "1; mode=block"

        # Enforce HTTPS (only in production)
        if os.getenv("ENVIRONMENT") != "development":
            response.headers["Strict-Transport-Security"] = (
                "max-age=31536000; includeSubDomains"
            )

        # Content Security Policy
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' 'unsafe-eval'; "
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data: https:; "
            "font-src 'self' https:; "
            "connect-src 'self' https:; "
            "frame-ancestors 'none';"
        )

        # Referrer policy
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

        # Permissions policy (disable unnecessary features)
        response.headers["Permissions-Policy"] = (
            "accelerometer=(), "
            "camera=(), "
            "geolocation=(), "
            "gyroscope=(), "
            "magnetometer=(), "
            "microphone=(), "
            "payment=(), "
            "usb=()"
        )

        return response


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Rate limiting middleware using sliding window algorithm.

    Limits requests per IP address to prevent abuse.
    Stores request counts in memory (for single-instance deployment).
    For production with multiple instances, use Redis-based rate limiting.
    """

    def __init__(self, app, requests_per_minute: int = 60):
        super().__init__(app)
        self.requests_per_minute = requests_per_minute
        self.window_size = 60  # 1 minute window
        self.request_counts: Dict[str, list] = defaultdict(list)

    def _get_client_ip(self, request: Request) -> str:
        """
        Get client IP address, handling proxies.

        SECURITY NOTE: X-Forwarded-For can be spoofed.
        In production, configure your reverse proxy to set a trusted header.
        """
        # Check for forwarded headers (from reverse proxy)
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            # Take the first IP (original client)
            return forwarded.split(",")[0].strip()

        # Check for real IP header (nginx)
        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip

        # Fallback to direct connection IP
        if request.client:
            return request.client.host

        return "unknown"

    def _clean_old_requests(self, ip: str, current_time: float) -> None:
        """Remove requests outside the current window"""
        cutoff = current_time - self.window_size
        self.request_counts[ip] = [
            t for t in self.request_counts[ip] if t > cutoff
        ]

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Skip rate limiting for health checks
        if request.url.path in ["/health", "/", "/docs", "/redoc", "/openapi.json"]:
            return await call_next(request)

        client_ip = self._get_client_ip(request)
        current_time = time.time()

        # Clean old requests
        self._clean_old_requests(client_ip, current_time)

        # Check rate limit
        if len(self.request_counts[client_ip]) >= self.requests_per_minute:
            # Calculate retry-after
            oldest_request = min(self.request_counts[client_ip])
            retry_after = int(oldest_request + self.window_size - current_time)

            return Response(
                content='{"error": "Rate limit exceeded", "retry_after": ' + str(retry_after) + "}",
                status_code=429,
                media_type="application/json",
                headers={"Retry-After": str(retry_after)},
            )

        # Record this request
        self.request_counts[client_ip].append(current_time)

        # Add rate limit headers
        response = await call_next(request)
        remaining = self.requests_per_minute - len(self.request_counts[client_ip])
        response.headers["X-RateLimit-Limit"] = str(self.requests_per_minute)
        response.headers["X-RateLimit-Remaining"] = str(max(0, remaining))
        response.headers["X-RateLimit-Reset"] = str(int(current_time + self.window_size))

        return response


# API Key validation
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


async def validate_api_key(
    request: Request,
    api_key: Optional[str] = None,
) -> bool:
    """
    Validate API key from header.

    Uses constant-time comparison to prevent timing attacks.

    Args:
        request: The incoming request
        api_key: API key from X-API-Key header

    Returns:
        True if valid, raises HTTPException if invalid

    Security:
        - Uses hmac.compare_digest for constant-time comparison
        - Never logs the actual API key
        - Returns generic error message
    """
    # Check if API key validation is required
    if os.getenv("API_KEY_REQUIRED", "false").lower() != "true":
        return True

    # Get expected API key from environment
    expected_key = os.getenv("API_KEY")
    if not expected_key:
        # No API key configured - allow access in development
        if os.getenv("ENVIRONMENT") == "development":
            return True
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="API key not configured",
        )

    # Check if API key was provided
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API key required",
            headers={"WWW-Authenticate": "ApiKey"},
        )

    # Constant-time comparison to prevent timing attacks
    if not hmac.compare_digest(api_key.encode(), expected_key.encode()):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
            headers={"WWW-Authenticate": "ApiKey"},
        )

    return True


def sanitize_input(value: str, max_length: int = 10000) -> str:
    """
    Sanitize user input to prevent injection attacks.

    Args:
        value: The input string to sanitize
        max_length: Maximum allowed length

    Returns:
        Sanitized string
    """
    if not value:
        return ""

    # Truncate to max length
    value = value[:max_length]

    # Remove null bytes
    value = value.replace("\x00", "")

    # Basic HTML entity encoding for XSS prevention
    # Note: For full XSS protection, use proper HTML escaping in templates
    value = value.replace("<", "&lt;").replace(">", "&gt;")

    return value


def validate_file_extension(filename: str, allowed_extensions: set) -> bool:
    """
    Validate file extension against whitelist.

    Args:
        filename: The filename to check
        allowed_extensions: Set of allowed extensions (without dot)

    Returns:
        True if valid, False otherwise
    """
    if not filename or "." not in filename:
        return False

    extension = filename.rsplit(".", 1)[-1].lower()
    return extension in allowed_extensions


# Allowed file extensions for bioinformatics data
ALLOWED_FILE_EXTENSIONS = {
    # Sequence data
    "fastq", "fq", "fasta", "fa", "fna", "ffn", "faa",
    # Alignment data
    "bam", "sam", "cram",
    # Variant data
    "vcf", "bcf", "gvcf",
    # Annotation data
    "bed", "gff", "gff3", "gtf",
    # Single-cell data
    "h5ad", "h5", "hdf5", "mtx", "loom",
    # Structure data
    "pdb", "cif", "mmcif",
    # Tabular data
    "csv", "tsv", "txt", "xlsx", "xls",
    # Compressed
    "gz", "zip", "tar", "bz2",
    # Other
    "json", "yaml", "yml", "parquet",
}
