"""Custom exceptions for the PR Agent application."""


class PRAgentError(Exception):
    """Base exception for all PR Agent errors."""

    pass


class ConfigurationError(PRAgentError):
    """Raised when there is a configuration issue."""

    pass


class GitHubAPIError(PRAgentError):
    """Raised when GitHub API calls fail."""

    def __init__(self, message: str, status_code: int = None, response: dict = None):
        self.status_code = status_code
        self.response = response
        super().__init__(message)


class WebhookVerificationError(PRAgentError):
    """Raised when webhook signature verification fails."""

    pass


class OpenAIServiceError(PRAgentError):
    """Raised when OpenAI API calls fail."""

    def __init__(self, message: str, error_code: str = None):
        self.error_code = error_code
        super().__init__(message)


class DiffParsingError(PRAgentError):
    """Raised when diff parsing fails."""

    pass


class CacheError(PRAgentError):
    """Raised when cache operations fail."""

    pass


class RateLimitExceeded(PRAgentError):
    """Raised when rate limit is exceeded."""

    pass


class InvalidPayloadError(PRAgentError):
    """Raised when webhook payload is invalid."""

    pass