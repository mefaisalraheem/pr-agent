"""Webhook service for handling GitHub pull request events."""

from typing import Optional

from fastapi import APIRouter, Request, HTTPException, status
from fastapi.responses import JSONResponse

from src.config import settings
from src.exceptions.custom_exceptions import (
    InvalidPayloadError,
    RateLimitExceeded,
    OpenAIServiceError,
    GitHubAPIError,
)
from src.models.schemas import WebhookPayload, PRSummary, CacheKey
from src.services.github_service import github_service
from src.services.openai_service import openai_service
from src.services.redis_service import redis_service
from src.utils.diff_parser import diff_parser
from src.utils.logger import get_logger, with_correlation_id

logger = get_logger(__name__)

# Rate limiting simple in-memory store (for demo)
# In production, use Redis for distributed rate limiting
from collections import defaultdict
import time

rate_limit_store = defaultdict(list)

webhook_router = APIRouter(tags=["Webhooks"])


def check_rate_limit(ip: str) -> bool:
    """
    Check if IP is rate limited.

    Args:
        ip: Client IP address

    Returns:
        True if allowed, False if rate limited
    """
    now = time.time()
    # Clean old entries
    rate_limit_store[ip] = [t for t in rate_limit_store[ip] if now - t < 60]

    if len(rate_limit_store[ip]) >= settings.MAX_REQUESTS_PER_MINUTE:
        logger.warning(f"Rate limit exceeded for IP: {ip}")
        return False

    rate_limit_store[ip].append(now)
    return True


@webhook_router.post("/github")
async def handle_github_webhook(request: Request) -> JSONResponse:
    """
    Handle GitHub webhook events.

    Args:
        request: FastAPI request object

    Returns:
        JSONResponse with status
    """
    # Get client IP for rate limiting
    client_ip = request.client.host if request.client else "unknown"

    # Rate limiting
    if not check_rate_limit(client_ip):
        raise RateLimitExceeded("Rate limit exceeded")

    # Get payload and headers
    try:
        payload_body = await request.body()
        signature = request.headers.get("X-Hub-Event")
        delivery_id = request.headers.get("X-GitHub-Delivery", "unknown")
    except Exception as e:
        logger.error(f"Failed to read request: {str(e)}")
        raise HTTPException(status_code=400, detail="Invalid request")

    # Verify webhook signature
    try:
        await github_service.verify_webhook_signature(
            payload_body,
            request.headers.get("X-Hub-Signature-256"),
        )
    except Exception as e:
        logger.warning(f"Webhook verification failed: {str(e)}")
        raise HTTPException(status_code=401, detail="Invalid signature")

    # Parse payload
    try:
        data = await request.json()
        payload = WebhookPayload(**data)
        logger.info(f"Received webhook: {payload.action} - PR #{payload.number}")
    except Exception as e:
        logger.error(f"Failed to parse webhook payload: {str(e)}")
        raise InvalidPayloadError(f"Invalid payload: {str(e)}")

    # Only process relevant actions
    valid_actions = ["opened", "synchronize", "ready_for_review", "reopened"]
    if payload.action.value not in valid_actions:
        logger.debug(f"Ignoring action: {payload.action}")
        return JSONResponse(
            status_code=200,
            content={"message": f"Ignored action: {payload.action}"},
        )

    # Process PR asynchronously
    try:
        # Extract repo info
        repo_full_name = payload.repository.full_name
        owner, repo = repo_full_name.split("/")
        pr_number = payload.number
        pr_data = payload.pull_request

        logger.info(f"Processing PR #{pr_number} from {repo_full_name}")

        # Check cache
        cache_key = CacheKey(
            pr_id=pr_data.id,
            repo_name=repo_full_name,
            commit_sha=pr_data.head.get("sha") if pr_data.head else None,
        ).to_key()

        # Try to get from cache
        cached_summary = await redis_service.get(cache_key)
        if cached_summary:
            logger.info(f"Using cached summary for PR #{pr_number}")
            # Parse cached summary
            try:
                summary = PRSummary(**cached_summary)
                # Post comment with cached data
                await _post_pr_summary(owner, repo, pr_number, summary)
                return JSONResponse(
                    status_code=200,
                    content={"message": "PR analyzed (cached)", "cached": True},
                )
            except Exception as e:
                logger.warning(f"Failed to parse cached summary: {str(e)}")
                # Continue to regenerate

        # Get PR diff
        diff = await github_service.get_pull_request_diff(owner, repo, pr_number)
        logger.debug(f"Retrieved diff: {len(diff)} characters")

        # Filter diff
        filtered_diff = diff_parser.filter_diff(diff)
        logger.debug(f"Filtered diff: {len(filtered_diff)} characters")

        # Get PR details
        pr = await github_service.get_pull_request(owner, repo, pr_number)

        # Analyze with OpenAI
        summary = await openai_service.analyze_pull_request(
            pr_title=pr.title,
            pr_description=pr.body or "",
            diff=filtered_diff,
        )

        # Cache the summary
        await redis_service.set(
            cache_key,
            summary.model_dump(),
            ttl=settings.REDIS_TTL,
        )

        # Post comment and labels to PR
        await _post_pr_summary(owner, repo, pr_number, summary)

        logger.info(f"Successfully processed PR #{pr_number}")
        return JSONResponse(
            status_code=200,
            content={"message": "PR analyzed successfully", "cached": False},
        )

    except OpenAIServiceError as e:
        logger.error(f"OpenAI service error for PR #{pr_number}: {str(e)}")
        # Try to post error comment
        try:
            await _post_error_comment(owner, repo, pr_number, "AI service temporarily unavailable")
        except Exception:
            pass
        raise

    except GitHubAPIError as e:
        logger.error(f"GitHub API error for PR #{pr_number}: {str(e)}")
        raise

    except Exception as e:
        logger.error(f"Unexpected error processing PR #{pr_number}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


async def _post_pr_summary(owner: str, repo: str, pr_number: int, summary: PRSummary) -> None:
    """
    Post PR summary as a comment and add labels.

    Args:
        owner: Repository owner
        repo: Repository name
        pr_number: Pull request number
        summary: PRSummary object
    """
    # Generate comment body
    comment_body = await openai_service.generate_comment_body(summary)

    # Post comment
    await github_service.create_pr_comment(owner, repo, pr_number, comment_body)
    logger.info(f"Posted summary comment on PR #{pr_number}")

    # Add labels if enabled
    if settings.ENABLE_PR_LABELING and summary.labels:
        try:
            await github_service.add_labels_to_pr(owner, repo, pr_number, summary.labels)
            logger.info(f"Added labels to PR #{pr_number}: {summary.labels}")
        except GitHubAPIError as e:
            logger.warning(f"Failed to add labels to PR #{pr_number}: {str(e)}")


async def _post_error_comment(owner: str, repo: str, pr_number: int, error_msg: str) -> None:
    """
    Post an error comment on the PR.

    Args:
        owner: Repository owner
        repo: Repository name
        pr_number: Pull request number
        error_msg: Error message
    """
    comment = f"""## 🤖 PR-Agent Error

I encountered an issue while analyzing this PR:

> ⚠️ {error_msg}

Please try again later or contact the repository maintainer.

---
*This is an automated message from PR-Agent 🤖*
"""
    await github_service.create_pr_comment(owner, repo, pr_number, comment)