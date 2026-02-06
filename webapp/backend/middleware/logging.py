"""
Request logging middleware for BioAgent Web API
Provides structured logging for monitoring and debugging
"""

import os
import time
import uuid
import json
import logging
from datetime import datetime
from typing import Callable

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response


# Configure logger
logger = logging.getLogger("bioagent.api")
logger.setLevel(logging.INFO)

# Create handler if not exists
if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(
        logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
    )
    logger.addHandler(handler)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """
    Logs all HTTP requests with timing and metadata.

    Logs include:
    - Request ID (for tracing)
    - HTTP method and path
    - Response status code
    - Request duration
    - Client IP (anonymized in production)

    Sensitive data is NOT logged:
    - Request/response bodies
    - Authorization headers
    - API keys
    """

    SENSITIVE_HEADERS = {
        "authorization",
        "x-api-key",
        "cookie",
        "set-cookie",
    }

    SENSITIVE_PATHS = {
        "/api/auth",
        "/api/users",
    }

    def __init__(self, app):
        super().__init__(app)
        self.is_production = os.getenv("ENVIRONMENT") != "development"

    def _get_client_ip(self, request: Request) -> str:
        """Get client IP, anonymizing in production"""
        ip = "unknown"

        # Get IP from headers or connection
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            ip = forwarded.split(",")[0].strip()
        elif request.client:
            ip = request.client.host

        # Anonymize in production
        if self.is_production and ip != "unknown":
            parts = ip.split(".")
            if len(parts) == 4:
                # IPv4: mask last octet
                ip = f"{parts[0]}.{parts[1]}.{parts[2]}.xxx"
            elif ":" in ip:
                # IPv6: mask last 64 bits
                ip = ip.rsplit(":", 4)[0] + ":xxxx:xxxx:xxxx:xxxx"

        return ip

    def _filter_headers(self, headers: dict) -> dict:
        """Remove sensitive headers from logging"""
        return {
            k: v
            for k, v in headers.items()
            if k.lower() not in self.SENSITIVE_HEADERS
        }

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Generate request ID for tracing
        request_id = str(uuid.uuid4())[:8]
        request.state.request_id = request_id

        # Skip logging for health checks and static files
        if request.url.path in ["/health", "/favicon.ico"]:
            return await call_next(request)

        # Start timing
        start_time = time.time()

        # Log request
        client_ip = self._get_client_ip(request)
        logger.info(
            f"[{request_id}] {request.method} {request.url.path} "
            f"from {client_ip}"
        )

        # Process request
        try:
            response = await call_next(request)
            duration = time.time() - start_time

            # Log response
            log_level = (
                logging.WARNING if response.status_code >= 400
                else logging.INFO
            )
            logger.log(
                log_level,
                f"[{request_id}] {response.status_code} "
                f"in {duration:.3f}s"
            )

            # Add request ID to response headers for debugging
            response.headers["X-Request-ID"] = request_id

            return response

        except Exception as e:
            duration = time.time() - start_time
            logger.error(
                f"[{request_id}] ERROR after {duration:.3f}s: {str(e)}"
            )
            raise


class AuditLogger:
    """
    Audit logger for security-relevant events.

    Logs to separate audit log file for compliance and security monitoring.
    """

    def __init__(self, log_file: str = "logs/audit.log"):
        self.logger = logging.getLogger("bioagent.audit")
        self.logger.setLevel(logging.INFO)

        # Create logs directory if needed
        os.makedirs(os.path.dirname(log_file), exist_ok=True)

        # File handler for audit log
        if not any(isinstance(h, logging.FileHandler) for h in self.logger.handlers):
            handler = logging.FileHandler(log_file)
            handler.setFormatter(
                logging.Formatter(
                    "%(asctime)s - %(levelname)s - %(message)s"
                )
            )
            self.logger.addHandler(handler)

    def log_auth_event(
        self,
        event_type: str,
        user_id: str,
        success: bool,
        ip_address: str,
        details: dict = None,
    ):
        """Log authentication-related events"""
        self.logger.info(
            json.dumps({
                "type": "auth",
                "event": event_type,
                "user_id": user_id,
                "success": success,
                "ip": ip_address,
                "details": details or {},
                "timestamp": datetime.utcnow().isoformat(),
            })
        )

    def log_data_access(
        self,
        user_id: str,
        resource_type: str,
        resource_id: str,
        action: str,
        ip_address: str,
    ):
        """Log data access events"""
        self.logger.info(
            json.dumps({
                "type": "data_access",
                "user_id": user_id,
                "resource_type": resource_type,
                "resource_id": resource_id,
                "action": action,
                "ip": ip_address,
                "timestamp": datetime.utcnow().isoformat(),
            })
        )

    def log_admin_action(
        self,
        admin_id: str,
        action: str,
        target: str,
        ip_address: str,
        details: dict = None,
    ):
        """Log administrative actions"""
        self.logger.warning(
            json.dumps({
                "type": "admin",
                "admin_id": admin_id,
                "action": action,
                "target": target,
                "ip": ip_address,
                "details": details or {},
                "timestamp": datetime.utcnow().isoformat(),
            })
        )


# Global audit logger instance
audit_logger = AuditLogger()
