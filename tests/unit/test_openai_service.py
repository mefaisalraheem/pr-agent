"""Unit tests for OpenAI service."""

import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.services.openai_service import openai_service
from src.models.schemas import PRSummary
from src.exceptions.custom_exceptions import OpenAIServiceError


class TestOpenAIService:
    """Test suite for OpenAIService."""

    @pytest.mark.asyncio
    async def test_build_prompt(self):
        """Test prompt building."""
        prompt = openai_service._build_prompt(
            pr_title="Test PR",
            pr_description="This is a test",
            diff="+print('hello')"
        )

        assert "Test PR" in prompt
        assert "This is a test" in prompt
        assert "print('hello')" in prompt
        assert "JSON format" in prompt

    @pytest.mark.asyncio
    async def test_build_prompt_with_empty_description(self):
        """Test prompt building with empty description."""
        prompt = openai_service._build_prompt(
            pr_title="Test PR",
            pr_description="",
            diff="+print('hello')"
        )

        assert "No description provided" in prompt

    @pytest.mark.asyncio
    async def test_parse_response_valid(self):
        """Test parsing valid response."""
        mock_response = MagicMock()
        mock_response.choices = [
            MagicMock(
                message=MagicMock(
                    content=json.dumps({
                        "summary": "- Point 1\n- Point 2",
                        "breaking_changes": ["Breaking change"],
                        "estimated_review_time": "5-10 minutes",
                        "suggested_reviewers": ["reviewer1"],
                        "labels": ["feature"],
                    })
                )
            )
        ]

        summary = openai_service._parse_response(mock_response)

        assert isinstance(summary, PRSummary)
        assert "- Point 1" in summary.summary
        assert "Breaking change" in summary.breaking_changes[0]
        assert summary.estimated_review_time == "5-10 minutes"
        assert "reviewer1" in summary.suggested_reviewers
        assert "feature" in summary.labels

    @pytest.mark.asyncio
    async def test_parse_response_with_markdown_code_blocks(self):
        """Test parsing response with markdown code blocks."""
        mock_response = MagicMock()
        mock_response.choices = [
            MagicMock(
                message=MagicMock(
                    content="```json\n" + json.dumps({
                        "summary": "- Test",
                        "breaking_changes": [],
                        "estimated_review_time": "5 minutes",
                        "suggested_reviewers": [],
                        "labels": [],
                    }) + "\n```"
                )
            )
        ]

        summary = openai_service._parse_response(mock_response)
        assert summary.summary == "- Test"

    @pytest.mark.asyncio
    async def test_parse_response_invalid_json(self):
        """Test parsing invalid JSON response."""
        mock_response = MagicMock()
        mock_response.choices = [
            MagicMock(
                message=MagicMock(
                    content="This is not JSON"
                )
            )
        ]

        with pytest.raises(OpenAIServiceError) as exc_info:
            openai_service._parse_response(mock_response)
        assert "Invalid JSON" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_parse_response_empty_content(self):
        """Test parsing empty response."""
        mock_response = MagicMock()
        mock_response.choices = [MagicMock(message=MagicMock(content=None))]

        with pytest.raises(OpenAIServiceError) as exc_info:
            openai_service._parse_response(mock_response)
        assert "Empty response" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_generate_comment_body_full(self):
        """Test generating full comment body."""
        summary = PRSummary(
            summary="- Point 1\n- Point 2\n- Point 3",
            breaking_changes=["Breaking change 1", "Breaking change 2"],
            estimated_review_time="10-15 minutes",
            suggested_reviewers=["alice", "bob"],
            labels=["feature", "enhancement", "test"],
        )

        comment = await openai_service.generate_comment_body(summary)

        assert "## 🤖 AI PR Summary" in comment
        assert "- Point 1" in comment
        assert "Breaking change 1" in comment
        assert "10-15 minutes" in comment
        assert "@alice" in comment
        assert "@bob" in comment
        assert "`feature`" in comment
        assert "`enhancement`" in comment

    @pytest.mark.asyncio
    async def test_generate_comment_body_minimal(self):
        """Test generating minimal comment body (no extras)."""
        summary = PRSummary(
            summary="- Only summary",
            breaking_changes=[],
            estimated_review_time="",
            suggested_reviewers=[],
            labels=[],
        )

        comment = await openai_service.generate_comment_body(summary)

        assert "## 🤖 AI PR Summary" in comment
        assert "- Only summary" in comment
        assert "Breaking Changes" not in comment
        assert "Estimated Review Time" not in comment
        assert "Suggested Reviewers" not in comment
        assert "Suggested Labels" not in comment

    @pytest.mark.asyncio
    @patch("src.services.openai_service.openai_service.client.chat.completions.create")
    async def test_analyze_pull_request_success(self, mock_create):
        """Test successful PR analysis."""
        # Mock OpenAI response
        mock_create.return_value = MagicMock(
            choices=[MagicMock(
                message=MagicMock(
                    content=json.dumps({
                        "summary": "- Test summary",
                        "breaking_changes": ["Breaking change"],
                        "estimated_review_time": "5 minutes",
                        "suggested_reviewers": ["reviewer1"],
                        "labels": ["bugfix"],
                    })
                )
            )],
            usage=MagicMock(
                prompt_tokens=100,
                completion_tokens=50,
                total_tokens=150
            )
        )

        summary = await openai_service.analyze_pull_request(
            pr_title="Test PR",
            pr_description="Test description",
            diff="+print('hello')"
        )

        assert isinstance(summary, PRSummary)
        assert "- Test summary" in summary.summary
        assert "Breaking change" in summary.breaking_changes[0]
        mock_create.assert_called_once()

    @pytest.mark.asyncio
    @patch("src.services.openai_service.openai_service.client.chat.completions.create")
    async def test_analyze_pull_request_retry(self, mock_create):
        """Test retry logic on failure."""
        # Fail first, succeed second
        mock_create.side_effect = [
            Exception("API error"),
            MagicMock(
                choices=[MagicMock(
                    message=MagicMock(
                        content=json.dumps({
                            "summary": "- Retry success",
                            "breaking_changes": [],
                            "estimated_review_time": "5 minutes",
                            "suggested_reviewers": [],
                            "labels": [],
                        })
                    )
                )],
                usage=MagicMock(
                    prompt_tokens=100,
                    completion_tokens=50,
                    total_tokens=150
                )
            )
        ]

        summary = await openai_service.analyze_pull_request(
            pr_title="Test PR",
            pr_description="Test description",
            diff="+print('hello')"
        )

        assert "- Retry success" in summary.summary
        assert mock_create.call_count == 2