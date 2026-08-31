"""Integration tests for webhook handling."""

import json
import pytest
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from src.main import app
from src.models.schemas import PRSummary


@pytest.mark.asyncio
async def test_webhook_integration_success(client: TestClient, sample_webhook_payload):
    """Test successful webhook processing."""
    # Mock the entire flow
    with patch("src.services.webhook_service.github_service") as mock_github, \
         patch("src.services.webhook_service.openai_service") as mock_openai, \
         patch("src.services.webhook_service.redis_service") as mock_redis:

        # Setup mocks
        mock_github.verify_webhook_signature = AsyncMock(return_value=True)
        mock_github.get_pull_request_diff = AsyncMock(return_value="diff --git a/test.py b/test.py\n+print('hello')")
        mock_github.get_pull_request = AsyncMock(return_value={
            "id": 123,
            "number": 1,
            "title": "Test PR",
            "body": "Test description",
            "head": {"sha": "abc123"},
            "user": {"login": "test"},
            "labels": [],
            "state": "open",
            "created_at": "2024-01-01T00:00:00Z",
            "updated_at": "2024-01-01T00:00:00Z",
            "html_url": "https://github.com/test/test/pull/1",
            "diff_url": "https://github.com/test/test/pull/1.diff",
            "patch_url": "https://github.com/test/test/pull/1.patch",
            "issue_url": "https://github.com/test/test/issues/1",
            "node_id": "PR_123",
            "closed_at": None,
            "merged_at": None,
            "merged": False,
            "mergeable": True,
            "mergeable_state": "clean",
            "comments": 0,
            "review_comments": 0,
            "commits": 1,
            "additions": 10,
            "deletions": 5,
            "changed_files": 2,
            "base": {"sha": "def456", "ref": "main"},
        })
        mock_github.create_pr_comment = AsyncMock(return_value={"id": 456})
        mock_github.add_labels_to_pr = AsyncMock(return_value={})

        mock_openai.analyze_pull_request = AsyncMock(return_value=PRSummary(
            summary="- Test summary point 1\n- Test summary point 2\n- Test summary point 3",
            breaking_changes=["Test breaking change"],
            estimated_review_time="5-10 minutes",
            suggested_reviewers=["reviewer1", "reviewer2"],
            labels=["feature", "enhancement"],
        ))
        mock_openai.generate_comment_body = AsyncMock(return_value="# AI Summary\nTest comment")

        mock_redis.get = AsyncMock(return_value=None)
        mock_redis.set = AsyncMock(return_value=True)

        # Send webhook
        headers = {
            "X-Hub-Signature-256": "test_signature",
            "X-GitHub-Event": "pull_request",
            "X-GitHub-Delivery": "test_delivery",
        }
        response = client.post(
            "/api/webhooks/github",
            json=sample_webhook_payload,
            headers=headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "PR analyzed successfully"
        assert data["cached"] is False

        # Verify calls
        mock_github.verify_webhook_signature.assert_called_once()
        mock_github.get_pull_request_diff.assert_called_once()
        mock_openai.analyze_pull_request.assert_called_once()
        mock_github.create_pr_comment.assert_called_once()
        mock_redis.set.assert_called_once()


@pytest.mark.asyncio
async def test_webhook_cached_response(client: TestClient, sample_webhook_payload):
    """Test webhook returns cached response."""
    with patch("src.services.webhook_service.github_service") as mock_github, \
         patch("src.services.webhook_service.openai_service") as mock_openai, \
         patch("src.services.webhook_service.redis_service") as mock_redis:

        mock_github.verify_webhook_signature = AsyncMock(return_value=True)

        # Return cached summary
        cached_summary = {
            "summary": "- Cached summary",
            "breaking_changes": [],
            "estimated_review_time": "5 minutes",
            "suggested_reviewers": [],
            "labels": ["bugfix"],
        }
        mock_redis.get = AsyncMock(return_value=cached_summary)
        mock_redis.set = AsyncMock(return_value=True)

        mock_github.get_pull_request_diff = AsyncMock(return_value="diff")
        mock_github.get_pull_request = AsyncMock(return_value={
            "id": 123,
            "number": 1,
            "title": "Test PR",
            "body": "Test description",
            "head": {"sha": "abc123"},
            "user": {"login": "test"},
            "labels": [],
            "state": "open",
            "created_at": "2024-01-01T00:00:00Z",
            "updated_at": "2024-01-01T00:00:00Z",
            "html_url": "https://github.com/test/test/pull/1",
            "diff_url": "https://github.com/test/test/pull/1.diff",
            "patch_url": "https://github.com/test/test/pull/1.patch",
            "issue_url": "https://github.com/test/test/issues/1",
            "node_id": "PR_123",
            "closed_at": None,
            "merged_at": None,
            "merged": False,
            "mergeable": True,
            "mergeable_state": "clean",
            "comments": 0,
            "review_comments": 0,
            "commits": 1,
            "additions": 10,
            "deletions": 5,
            "changed_files": 2,
            "base": {"sha": "def456", "ref": "main"},
        })
        mock_github.create_pr_comment = AsyncMock(return_value={"id": 456})
        mock_github.add_labels_to_pr = AsyncMock(return_value={})

        mock_openai.generate_comment_body = AsyncMock(return_value="# AI Summary\nCached comment")

        headers = {
            "X-Hub-Signature-256": "test_signature",
            "X-GitHub-Event": "pull_request",
        }
        response = client.post(
            "/api/webhooks/github",
            json=sample_webhook_payload,
            headers=headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "PR analyzed (cached)"
        assert data["cached"] is True

        # OpenAI should NOT be called for cached response
        mock_openai.analyze_pull_request.assert_not_called()


@pytest.mark.asyncio
async def test_webhook_invalid_signature(client: TestClient, sample_webhook_payload):
    """Test webhook with invalid signature."""
    with patch("src.services.webhook_service.github_service.verify_webhook_signature") as mock_verify:
        mock_verify.side_effect = Exception("Invalid signature")

        headers = {
            "X-Hub-Signature-256": "invalid_signature",
            "X-GitHub-Event": "pull_request",
        }
        response = client.post(
            "/api/webhooks/github",
            json=sample_webhook_payload,
            headers=headers,
        )

        assert response.status_code == 401
        assert "Invalid signature" in response.text


@pytest.mark.asyncio
async def test_webhook_rate_limit(client: TestClient, sample_webhook_payload):
    """Test rate limiting."""
    with patch("src.services.webhook_service.rate_limit_store", {}):
        headers = {
            "X-Hub-Signature-256": "test_signature",
            "X-GitHub-Event": "pull_request",
        }

        # Send many requests quickly
        for _ in range(65):  # Exceeds limit
            response = client.post(
                "/api/webhooks/github",
                json=sample_webhook_payload,
                headers=headers,
            )

        # Last request should be rate limited
        assert response.status_code == 429
        assert "Rate limit exceeded" in response.text


@pytest.mark.asyncio
async def test_webhook_ignored_action(client: TestClient, sample_webhook_payload):
    """Test ignored webhook actions."""
    # Modify action to ignored one
    sample_webhook_payload["action"] = "closed"

    with patch("src.services.webhook_service.github_service.verify_webhook_signature") as mock_verify:
        mock_verify.return_value = True

        headers = {
            "X-Hub-Signature-256": "test_signature",
            "X-GitHub-Event": "pull_request",
        }
        response = client.post(
            "/api/webhooks/github",
            json=sample_webhook_payload,
            headers=headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert "Ignored action" in data["message"]