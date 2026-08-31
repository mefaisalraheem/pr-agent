"""Pydantic models for request/response validation."""

from datetime import datetime
from enum import Enum
from typing import List, Optional, Dict, Any

from pydantic import BaseModel, Field, HttpUrl, field_validator


class PullRequestAction(str, Enum):
    """GitHub pull request actions."""

    OPENED = "opened"
    EDITED = "edited"
    CLOSED = "closed"
    REOPENED = "reopened"
    ASSIGNED = "assigned"
    UNASSIGNED = "unassigned"
    REVIEW_REQUESTED = "review_requested"
    REVIEW_REQUEST_REMOVED = "review_request_removed"
    LABELED = "labeled"
    UNLABELED = "unlabeled"
    SYNCHRONIZE = "synchronize"
    READY_FOR_REVIEW = "ready_for_review"


class GitHubUser(BaseModel):
    """GitHub user model."""

    login: str
    id: int
    node_id: str
    avatar_url: HttpUrl
    html_url: HttpUrl
    type: str
    site_admin: bool


class GitHubRepository(BaseModel):
    """GitHub repository model."""

    id: int
    node_id: str
    name: str
    full_name: str
    private: bool
    html_url: HttpUrl
    description: Optional[str] = None
    default_branch: str


class GitHubPullRequest(BaseModel):
    """GitHub pull request model."""

    id: int
    node_id: str
    number: int
    state: str
    title: str
    body: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    closed_at: Optional[datetime] = None
    merged_at: Optional[datetime] = None
    html_url: HttpUrl
    diff_url: HttpUrl
    patch_url: HttpUrl
    issue_url: HttpUrl
    user: GitHubUser
    labels: List[Dict[str, Any]] = Field(default_factory=list)
    head: Dict[str, Any]  # Branch info
    base: Dict[str, Any]  # Base branch info
    merged: bool = False
    mergeable: Optional[bool] = None
    mergeable_state: Optional[str] = None
    comments: int = 0
    review_comments: int = 0
    commits: int = 0
    additions: int = 0
    deletions: int = 0
    changed_files: int = 0


class WebhookPayload(BaseModel):
    """GitHub webhook payload model."""

    action: PullRequestAction
    number: int
    pull_request: GitHubPullRequest
    repository: GitHubRepository
    sender: GitHubUser
    installation: Optional[Dict[str, Any]] = None

    @field_validator("action", mode="before")
    @classmethod
    def validate_action(cls, value: str) -> PullRequestAction:
        """Convert string to PullRequestAction enum."""
        try:
            return PullRequestAction(value)
        except ValueError:
            raise ValueError(f"Invalid pull request action: {value}")


class FileChange(BaseModel):
    """Model for a changed file in a PR."""

    filename: str
    status: str  # added, modified, removed, renamed
    additions: int
    deletions: int
    changes: int
    patch: Optional[str] = None
    raw_url: Optional[HttpUrl] = None
    is_binary: bool = False


class PRSummary(BaseModel):
    """Model for the AI-generated PR summary."""

    summary: str
    breaking_changes: Optional[List[str]] = Field(default_factory=list)
    estimated_review_time: Optional[str] = None
    suggested_reviewers: Optional[List[str]] = Field(default_factory=list)
    labels: Optional[List[str]] = Field(default_factory=list)

    class Config:
        json_schema_extra = {
            "example": {
                "summary": "1. Refactored authentication middleware\n"
                "2. Added Redis caching for user profiles\n"
                "3. Fixed null pointer in login flow",
                "breaking_changes": ["Auth middleware now requires JWT in headers"],
                "estimated_review_time": "15-20 minutes",
                "suggested_reviewers": ["alice", "bob"],
                "labels": ["enhancement", "needs-review"],
            }
        }


class CacheKey(BaseModel):
    """Model for cache key generation."""

    pr_id: int
    repo_name: str
    commit_sha: Optional[str] = None
    version: int = 1

    def to_key(self) -> str:
        """Generate cache key string."""
        base = f"pr:{self.repo_name}:{self.pr_id}"
        if self.commit_sha:
            return f"{base}:{self.commit_sha}"
        return base


class HealthCheckResponse(BaseModel):
    """Health check response model."""

    status: str = "healthy"
    version: str = "1.0.0"
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    redis_connected: bool
    openai_configured: bool


class ErrorResponse(BaseModel):
    """Standard error response model."""

    error: str
    message: str
    status_code: int
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    correlation_id: Optional[str] = None