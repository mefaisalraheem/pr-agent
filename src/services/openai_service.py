"""OpenAI service with prompt engineering and response parsing."""

import json
from typing import Optional, Dict, Any, List

from openai import AsyncOpenAI
from openai.types.chat import ChatCompletion
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log,
)

from src.config import settings, OpenAIModel
from src.exceptions.custom_exceptions import OpenAIServiceError
from src.models.schemas import PRSummary
from src.utils.logger import get_logger

logger = get_logger(__name__)


class OpenAIService:
    """Service for interacting with OpenAI API."""

    def __init__(self):
        self.client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        self.model = settings.OPENAI_MODEL.value
        self.temperature = settings.OPENAI_TEMPERATURE
        self.max_tokens = settings.OPENAI_MAX_TOKENS

    def _build_prompt(self, pr_title: str, pr_description: str, diff: str) -> str:
        """
        Build the prompt for OpenAI.

        Args:
            pr_title: Pull request title
            pr_description: Pull request description
            diff: Filtered diff content

        Returns:
            Formatted prompt string
        """
        # If description is empty, provide a placeholder
        description = pr_description or "No description provided"

        # Truncate diff if too long (safety measure)
        if len(diff) > 15000:
            diff = diff[:15000] + "\n... (diff truncated)"

        prompt = f"""You are a senior software engineer reviewing a pull request. Analyze the following PR and provide a concise summary.

PR Title: {pr_title}
PR Description: {description}

Changes:
{diff}

Please provide your analysis in the following JSON format:
{{
    "summary": "A 3-bullet-point summary of the key changes (max 3 bullets, each bullet max 100 characters)",
    "breaking_changes": ["List any breaking changes (empty list if none)"],
    "estimated_review_time": "Estimated review time in minutes (e.g., '10-15 minutes')",
    "suggested_reviewers": ["List of 2-3 GitHub usernames who should review this PR based on the code areas"],
    "labels": ["Suggested labels from: bugfix, feature, enhancement, documentation, refactor, tests, performance, dependencies"]
}}

Rules:
1. Keep the summary concise and focused on WHAT changed, not HOW
2. Identify breaking changes that could affect other parts of the system
3. Estimate review time based on complexity and number of files changed
4. Suggest reviewers who are familiar with the changed code areas
5. Only use the labels from the allowed list above
6. If unsure about any field, use reasonable defaults
7. Return ONLY valid JSON, no other text

Now provide the analysis:"""

        return prompt

    def _parse_response(self, response: ChatCompletion) -> PRSummary:
        """
        Parse OpenAI response into PRSummary.

        Args:
            response: OpenAI chat completion response

        Returns:
            Parsed PRSummary object

        Raises:
            OpenAIServiceError: If response parsing fails
        """
        try:
            content = response.choices[0].message.content

            if not content:
                raise OpenAIServiceError("Empty response from OpenAI")

            # Try to extract JSON from the response
            # Sometimes the model adds markdown code blocks
            content = content.strip()
            if content.startswith("```json"):
                content = content[7:]
            if content.startswith("```"):
                content = content[3:]
            if content.endswith("```"):
                content = content[:-3]
            content = content.strip()

            # Parse JSON
            data = json.loads(content)

            # Validate and create PRSummary
            summary = PRSummary(
                summary=data.get("summary", "No summary provided"),
                breaking_changes=data.get("breaking_changes", []),
                estimated_review_time=data.get("estimated_review_time", "Unknown"),
                suggested_reviewers=data.get("suggested_reviewers", []),
                labels=data.get("labels", []),
            )

            logger.info(f"Successfully parsed OpenAI response with {len(summary.labels)} labels")
            return summary

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse OpenAI response as JSON: {str(e)}")
            logger.debug(f"Raw response: {content[:200]}...")
            raise OpenAIServiceError(f"Invalid JSON response from OpenAI: {str(e)}")
        except Exception as e:
            logger.error(f"Unexpected error parsing OpenAI response: {str(e)}")
            raise OpenAIServiceError(f"Response parsing failed: {str(e)}")

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=15),
        retry=retry_if_exception_type((OpenAIServiceError,)),
        before_sleep=before_sleep_log(logger, logger.warning),
    )
    async def analyze_pull_request(
        self,
        pr_title: str,
        pr_description: str,
        diff: str,
    ) -> PRSummary:
        """
        Analyze a pull request using OpenAI.

        Args:
            pr_title: Pull request title
            pr_description: Pull request description
            diff: Filtered diff content

        Returns:
            PRSummary object with analysis results

        Raises:
            OpenAIServiceError: If OpenAI API call fails
        """
        try:
            prompt = self._build_prompt(pr_title, pr_description, diff)

            # Log prompt length for monitoring
            logger.debug(f"Prompt length: {len(prompt)} characters")

            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are a senior software engineer specializing in code review. Provide concise, actionable analysis.",
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=self.temperature,
                max_tokens=self.max_tokens,
                response_format={"type": "json_object"} if self.model != OpenAIModel.GPT35_TURBO else None,
            )

            # Parse and return the response
            summary = self._parse_response(response)

            # Log token usage
            usage = response.usage
            if usage:
                logger.info(
                    f"OpenAI token usage - Prompt: {usage.prompt_tokens}, "
                    f"Completion: {usage.completion_tokens}, Total: {usage.total_tokens}"
                )

            return summary

        except OpenAIServiceError:
            # Re-raise the error for retry
            raise
        except Exception as e:
            logger.error(f"OpenAI API call failed: {str(e)}")
            raise OpenAIServiceError(f"OpenAI API error: {str(e)}")

    async def generate_comment_body(self, summary: PRSummary) -> str:
        """
        Generate a formatted comment body for the PR.

        Args:
            summary: PRSummary object

        Returns:
            Formatted markdown comment
        """
        # Build summary bullets
        summary_lines = summary.summary.strip().split("\n")
        if len(summary_lines) == 1 and not summary_lines[0].startswith("-"):
            # If summary is a single line, split by numbers or bullets
            import re

            parts = re.split(r"[\d\.\-\*]\s*", summary_lines[0])
            parts = [p.strip() for p in parts if p.strip()]
            summary_lines = parts

        # Format bullets
        bullets = "\n".join(f"- {line}" for line in summary_lines if line.strip())

        # Build the comment
        comment = f"""## 🤖 AI PR Summary

### 📝 Key Changes
{bullets or "No summary available"}

### 🔍 Analysis Details
"""

        # Add breaking changes if enabled
        if settings.ENABLE_BREAKING_CHANGE_DETECTION and summary.breaking_changes:
            breaking = "\n".join(f"- ⚠️ {change}" for change in summary.breaking_changes)
            comment += f"""
### ⚠️ Breaking Changes
{breaking}
"""

        # Add estimated review time if enabled
        if settings.ENABLE_REVIEW_TIME_ESTIMATION and summary.estimated_review_time:
            comment += f"""
### ⏱️ Estimated Review Time
{summary.estimated_review_time}
"""

        # Add suggested reviewers if enabled
        if settings.ENABLE_REVIEWER_SUGGESTION and summary.suggested_reviewers:
            reviewers = ", ".join(f"@{reviewer}" for reviewer in summary.suggested_reviewers)
            comment += f"""
### 👥 Suggested Reviewers
{reviewers}
"""

        # Add labels if enabled
        if settings.ENABLE_PR_LABELING and summary.labels:
            labels = ", ".join(f"`{label}`" for label in summary.labels)
            comment += f"""
### 🏷️ Suggested Labels
{labels}
"""

        comment += """
---
*This summary was automatically generated by PR-Agent 🤖*
"""

        return comment


# Singleton instance
openai_service = OpenAIService()