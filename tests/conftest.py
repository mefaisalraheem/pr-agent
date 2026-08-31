"""Pytest configuration and fixtures."""

import pytest
from typing import AsyncGenerator, Dict, Any
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, MagicMock

from src.main import app
from src.services.github_service import github_service
from src.services.openai_service import openai_service
from src.services.redis_service import redis_service


@pytest.fixture
def client() -> TestClient:
    """Create test client."""
    return TestClient(app)


@pytest.fixture
async def mock_redis() -> AsyncGenerator:
    """Mock Redis service."""
    original_get = redis_service.get
    original_set = redis_service.set

    redis_service.get = AsyncMock(return_value=None)
    redis_service.set = AsyncMock(return_value=True)
    redis_service.ping = AsyncMock(return_value=True)

    yield redis_service

    # Restore
    redis_service.get = original_get
    redis_service.set = original_set
    redis_service.ping = original_ping


@pytest.fixture
async def mock_github() -> AsyncGenerator:
    """Mock GitHub service."""
    original_get_pr = github_service.get_pull_request
    original_get_diff = github_service.get_pull_request_diff
    original_comment = github_service.create_pr_comment
    original_labels = github_service.add_labels_to_pr
    original_verify = github_service.verify_webhook_signature

    # Mock PR data
    mock_pr = {
        "id": 123,
        "node_id": "PR_kwDO...",
        "number": 1,
        "state": "open",
        "title": "Test PR",
        "body": "This is a test PR",
        "created_at": "2024-01-01T00:00:00Z",
        "updated_at": "2024-01-01T00:00:00Z",
        "closed_at": None,
        "merged_at": None,
        "html_url": "https://github.com/test/test/pull/1",
        "diff_url": "https://github.com/test/test/pull/1.diff",
        "patch_url": "https://github.com/test/test/pull/1.patch",
        "issue_url": "https://github.com/test/test/issues/1",
        "user": {
            "login": "testuser",
            "id": 123,
            "node_id": "MDQ6VXNlcjE=",
            "avatar_url": "https://avatars.githubusercontent.com/u/123",
            "html_url": "https://github.com/testuser",
            "type": "User",
            "site_admin": False,
        },
        "labels": [],
        "head": {"sha": "abc123", "ref": "feature/branch"},
        "base": {"sha": "def456", "ref": "main"},
        "merged": False,
        "mergeable": True,
        "mergeable_state": "clean",
        "comments": 0,
        "review_comments": 0,
        "commits": 1,
        "additions": 10,
        "deletions": 5,
        "changed_files": 2,
    }

    github_service.get_pull_request = AsyncMock(return_value=mock_pr)
    github_service.get_pull_request_diff = AsyncMock(
        return_value="diff --git a/file.py b/file.py\n+print('hello')"
    )
    github_service.create_pr_comment = AsyncMock(return_value={"id": 456})
    github_service.add_labels_to_pr = AsyncMock(return_value={})
    github_service.verify_webhook_signature = AsyncMock(return_value=True)

    yield github_service

    # Restore
    github_service.get_pull_request = original_get_pr
    github_service.get_pull_request_diff = original_get_diff
    github_service.create_pr_comment = original_comment
    github_service.add_labels_to_pr = original_labels
    github_service.verify_webhook_signature = original_verify


@pytest.fixture
async def mock_openai() -> AsyncGenerator:
    """Mock OpenAI service."""
    original_analyze = openai_service.analyze_pull_request
    original_comment = openai_service.generate_comment_body

    mock_summary = {
        "summary": "- Test summary point 1\n- Test summary point 2\n- Test summary point 3",
        "breaking_changes": ["Test breaking change"],
        "estimated_review_time": "5-10 minutes",
        "suggested_reviewers": ["reviewer1", "reviewer2"],
        "labels": ["feature", "enhancement"],
    }

    openai_service.analyze_pull_request = AsyncMock(return_value=mock_summary)
    openai_service.generate_comment_body = AsyncMock(
        return_value="## AI Summary\nTest comment"
    )

    yield openai_service

    # Restore
    openai_service.analyze_pull_request = original_analyze
    openai_service.generate_comment_body = original_comment


@pytest.fixture
def sample_webhook_payload() -> Dict[str, Any]:
    """Sample webhook payload for testing."""
    return {
        "action": "opened",
        "number": 1,
        "pull_request": {
            "id": 123,
            "node_id": "PR_kwDO...",
            "number": 1,
            "state": "open",
            "title": "Test PR",
            "body": "This is a test PR",
            "created_at": "2024-01-01T00:00:00Z",
            "updated_at": "2024-01-01T00:00:00Z",
            "closed_at": None,
            "merged_at": None,
            "html_url": "https://github.com/test/test/pull/1",
            "diff_url": "https://github.com/test/test/pull/1.diff",
            "patch_url": "https://github.com/test/test/pull/1.patch",
            "issue_url": "https://github.com/test/test/issues/1",
            "user": {
                "login": "testuser",
                "id": 123,
                "node_id": "MDQ6VXNlcjE=",
                "avatar_url": "https://avatars.githubusercontent.com/u/123",
                "html_url": "https://github.com/testuser",
                "type": "User",
                "site_admin": False,
            },
            "labels": [],
            "head": {"sha": "abc123", "ref": "feature/branch"},
            "base": {"sha": "def456", "ref": "main"},
            "merged": False,
            "mergeable": True,
            "mergeable_state": "clean",
            "comments": 0,
            "review_comments": 0,
            "commits": 1,
            "additions": 10,
            "deletions": 5,
            "changed_files": 2,
        },
        "repository": {
            "id": 456,
            "node_id": "R_kgDO...",
            "name": "test",
            "full_name": "test/test",
            "private": False,
            "html_url": "https://github.com/test/test",
            "description": "Test repo",
            "default_branch": "main",
        },
        "sender": {
            "login": "testuser",
            "id": 123,
            "node_id": "MDQ6VXNlcjE=",
            "avatar_url": "https://avatars.githubusercontent.com/u/123",
            "html_url": "https://github.com/testuser",
            "type": "User",
            "site_admin": False,
        },
    }