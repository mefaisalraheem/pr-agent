"""FastAPI application entry point."""

from contextlib import asynccontextmanager
from typing import Dict, Any

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from src.config import settings
from src.exceptions.custom_exceptions import (
    GitHubAPIError,
    WebhookVerificationError,
    OpenAIServiceError,
    RateLimitExceeded,
    InvalidPayloadError,
)
from src.models.schemas import HealthCheckResponse, ErrorResponse
from src.utils.logger import get_logger, with_correlation_id
from src.services.redis_service import redis_service
from src.services.webhook_service import webhook_router

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    # Startup
    logger.info("Starting PR Agent application...")
    logger.info(f"Environment: {settings.APP_ENV.value}")
    logger.info(f"OpenAI Model: {settings.OPENAI_MODEL.value}")
    logger.info(f"Redis URL: {settings.REDIS_URL}")

    # Test Redis connection
    try:
        await redis_service.ping()
        logger.info("Redis connection established successfully")
    except Exception as e:
        logger.error(f"Failed to connect to Redis: {str(e)}")
        # Don't fail startup if Redis is down, we can still function (just slower)

    yield

    # Shutdown
    logger.info("Shutting down PR Agent application...")
    await redis_service.close()


# Create FastAPI app
app = FastAPI(
    title="PR Agent - AI Code Summarizer",
    description="Automated Pull Request summarization using AI",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/api/docs" if settings.APP_DEBUG else None,
    redoc_url="/api/redoc" if settings.APP_DEBUG else None,
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if settings.APP_DEBUG else [],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(webhook_router, prefix="/api/webhooks", tags=["Webhooks"])


@app.get("/", tags=["Health"])
async def root() -> Dict[str, str]:
    """Root endpoint."""
    return {"message": "PR Agent is running", "status": "healthy"}


@app.get("/health", tags=["Health"], response_model=HealthCheckResponse)
async def health_check() -> HealthCheckResponse:
    """Health check endpoint."""
    # Check Redis connection
    redis_connected = False
    try:
        redis_connected = await redis_service.ping()
    except Exception:
        pass

    return HealthCheckResponse(
        redis_connected=redis_connected,
        openai_configured=bool(settings.OPENAI_API_KEY),
    )


@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    """Handle rate limit exceptions."""
    logger.warning(f"Rate limit exceeded: {str(exc)}")
    return JSONResponse(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        content=ErrorResponse(
            error="RateLimitExceeded",
            message="Too many requests. Please try again later.",
            status_code=429,
        ).model_dump(),
    )


@app.exception_handler(WebhookVerificationError)
async def webhook_verification_handler(
    request: Request, exc: WebhookVerificationError
) -> JSONResponse:
    """Handle webhook verification errors."""
    logger.error(f"Webhook verification failed: {str(exc)}")
    return JSONResponse(
        status_code=status.HTTP_401_UNAUTHORIZED,
        content=ErrorResponse(
            error="WebhookVerificationFailed",
            message="Invalid webhook signature",
            status_code=401,
        ).model_dump(),
    )


@app.exception_handler(GitHubAPIError)
async def github_error_handler(request: Request, exc: GitHubAPIError) -> JSONResponse:
    """Handle GitHub API errors."""
    logger.error(f"GitHub API error: {str(exc)}, status: {exc.status_code}")
    return JSONResponse(
        status_code=status.HTTP_502_BAD_GATEWAY,
        content=ErrorResponse(
            error="GitHubAPIError",
            message=f"GitHub API error: {str(exc)}",
            status_code=502,
        ).model_dump(),
    )


@app.exception_handler(OpenAIServiceError)
async def openai_error_handler(request: Request, exc: OpenAIServiceError) -> JSONResponse:
    """Handle OpenAI service errors."""
    logger.error(f"OpenAI API error: {str(exc)}, code: {exc.error_code}")
    return JSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        content=ErrorResponse(
            error="OpenAIServiceError",
            message="AI service temporarily unavailable",
            status_code=503,
        ).model_download(),
    )


@app.exception_handler(InvalidPayloadError)
async def invalid_payload_handler(request: Request, exc: InvalidPayloadError) -> JSONResponse:
    """Handle invalid payload errors."""
    logger.warning(f"Invalid payload: {str(exc)}")
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content=ErrorResponse(
            error="InvalidPayload",
            message=str(exc),
            status_code=400,
        ).model_dump(),
    )


@app.exception_handler(Exception)
async def generic_error_handler(request: Request, exc: Exception) -> JSONResponse:
    """Handle all unhandled exceptions."""
    logger.exception(f"Unhandled exception: {str(exc)}")
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=ErrorResponse(
            error="InternalServerError",
            message="An unexpected error occurred",
            status_code=500,
        ).model_dump(),
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "src.main:app",
        host="0.0.0.0",
        port=settings.APP_PORT,
        reload=settings.APP_DEBUG,
        log_level=settings.LOG_LEVEL.lower(),
    )