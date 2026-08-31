"""GitHub API service with robust error handling and retries."""

import hashlib
import hmac
from typing import Optional, List, Dict, Any

import httpx
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log,
)

from src.config import settings
from src.exceptions.custom_exceptions import (
    GitHubAPIError,
    WebhookVerificationError,
)
from src.models.schemas import FileChange, GitHubPullRequest
from src.utils.logger import get_logger

logger = get_logger(__name__)


class GitHubService:
    """Service for interacting with GitHub API."""

    def __init__(self):
        self.token = settings.GITHUB_TOKEN
        self.base_url = settings.GITHUB_API_BASE_URL
        self.timeout = settings.REQUEST_TIMEOUT_SECONDS
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client with authentication."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                timeout=self.timeout,
                headers={
                    "Authorization": f"Bearer {self.token}",
                    "Accept": "application/vnd.github.v3+json",
                },
            )
        return self._client

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((httpx.TimeoutException, httpx.NetworkError)),
        before_sleep=before_sleep_log(logger, logger.warning),
    )
    async def _make_request(
        self,
        method: str,
        endpoint: str,
        data: Optional[Dict] = None,
        params: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        """
        Make an HTTP request to GitHub API with retry logic.

        Args:
            method: HTTP method (GET, POST, etc.)
            endpoint: API endpoint
            data: Request body
            params: Query parameters

        Returns:
            JSON response

        Raises:
            GitHubAPIError: If the API request fails
        """
        client = await self._get_client()

        try:
            response = await client.request(
                method=method,
                url=endpoint,
                json=data,
                params=params,
            )

            # Handle rate limits
            if response.status_code == 403 and "rate limit" in response.text.lower():
                logger.warning("GitHub API rate limit exceeded")
                raise GitHubAPIError(
                    "GitHub API rate limit exceeded",
                    status_code=429,
                )

            if response.status_code >= 400:
                error_msg = f"GitHub API error: {response.status_code} - {response.text}"
                logger.error(error_msg)
                raise GitHubAPIError(
                    error_msg,
                    status_code=response.status_code,
                    response=response.json() if response.text else None,
                )

            return response.json() if response.text else {}

        except httpx.TimeoutException as e:
            logger.error(f"GitHub API timeout: {str(e)}")
            raise
        except httpx.NetworkError as e:
            logger.error(f"GitHub API network error: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"GitHub API unexpected error: {str(e)}")
            raise GitHubAPIError(f"GitHub API request failed: {str(e)}")

    async def get_pull_request(
        self,
        owner: str,
        repo: str,
        pr_number: int,
    ) -> GitHubPullRequest:
        """
        Get pull request details.

        Args:
            owner: Repository owner
            repo: Repository name
            pr_number: Pull request number

        Returns:
            PullRequest object
        """
        endpoint = f"/repos/{owner}/{repo}/pulls/{pr_number}"
        data = await self._make_request("GET", endpoint)

        # Parse and validate response
        try:
            return GitHubPullRequest(**data)
        except Exception as e:
            logger.error(f"Failed to parse pull request data: {str(e)}")
            raise GitHubAPIError(f"Invalid PR data: {str(e)}")

    async def get_pull_request_diff(
        self,
        owner: str,
        repo: str,
        pr_number: int,
    ) -> str:
        """
        Get pull request diff.

        Args:
            owner: Repository owner
            repo: Repository name
            pr_number: Pull request number

        Returns:
            Diff string
        """
        client = await self._get_client()
        endpoint = f"/repos/{owner}/{repo}/pulls/{pr_number}"

        try:
            response = await client.get(
                endpoint,
                headers={"Accept": "application/vnd.github.v3.diff"},
            )

            if response.status_code >= 400:
                error_msg = f"GitHub API diff error: {response.status_code}"
                logger.error(error_msg)
                raise GitHubAPIError(error_msg, status_code=response.status_code)

            return response.text

        except Exception as e:
            logger.error(f"Failed to get PR diff: {str(e)}")
            raise GitHubAPIError(f"Failed to get PR diff: {str(e)}")

    async def get_pr_files(
        self,
        owner: str,
        repo: str,
        pr_number: int,
    ) -> List[FileChange]:
        """
        Get list of changed files in PR.

        Args:
            owner: Repository owner
            repo: Repository name
            pr_number: Pull request number

        Returns:
            List of FileChange objects
        """
        endpoint = f"/repos/{owner}/{repo}/pulls/{pr_number}/files"
        data = await self._make_request("GET", endpoint)

        files = []
        for file_data in data:
            try:
                # Convert patch to None if not present
                if "patch" not in file_data:
                    file_data["patch"] = None
                files.append(FileChange(**file_data))
            except Exception as e:
                logger.warning(f"Failed to parse file data: {str(e)}")

        return files

    async def create_pr_comment(
        self,
        owner: str,
        repo: str,
        pr_number: int,
        body: str,
    ) -> Dict[str, Any]:
        """
        Create a comment on a pull request.

        Args:
            owner: Repository owner
            repo: Repository name
            pr_number: Pull request number
            body: Comment body

        Returns:
            Comment data
        """
        endpoint = f"/repos/{owner}/{repo}/issues/{pr_number}/comments"
        data = {"body": body}
        return await self._make_request("POST", endpoint, data=data)

    async def add_labels_to_pr(
        self,
        owner: str,
        repo: str,
        pr_number: int,
        labels: List[str],
    ) -> Dict[str, Any]:
        """
        Add labels to a pull request.

        Args:
            owner: Repository owner
            repo: Repository name
            pr_number: Pull request number
            labels: List of label names

        Returns:
            Response data
        """
        if not labels:
            return {}

        endpoint = f"/repos/{owner}/{repo}/issues/{pr_number}/labels"
        data = {"labels": labels}
        return await self._make_request("POST", endpoint, data=data)

    def verify_webhook_signature(
        self,
        payload_body: bytes,
        signature: Optional[str],
    ) -> bool:
        """
        Verify GitHub webhook signature.

        Args:
            payload_body: Raw request body
            signature: Signature header value

        Returns:
            True if valid, False otherwise

        Raises:
            WebhookVerificationError: If signature verification fails
        """
        if not signature:
            logger.warning("Webhook signature missing")
            raise WebhookVerificationError("Webhook signature missing")

        if not settings.GITHUB_WEBHOOK_SECRET:
            logger.warning("Webhook secret not configured")
            raise WebhookVerificationError("Webhook secret not configured")

        try:
            # Extract the signature value
            if signature.startswith("sha256="):
                signature = signature[7:]

            # Compute expected signature
            expected = hmac.new(
                settings.GITHUB_WEBHOOK_SECRET.encode("utf-8"),
                payload_body,
                hashlib.sha256,
            ).hexdigest()

            # Compare in constant time
            is_valid = hmac.compare_digest(signature, expected)

            if not is_valid:
                logger.warning("Webhook signature verification failed")
                raise WebhookVerificationError("Invalid webhook signature")

            logger.debug("Webhook signature verified successfully")
            return True

        except Exception as e:
            logger.error(f"Webhook verification error: {str(e)}")
            raise WebhookVerificationError(f"Verification error: {str(e)}")

    async def close(self) -> None:
        """Close HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None


# Singleton instance
github_service = GitHubService()