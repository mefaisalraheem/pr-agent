"""Smart diff parsing and filtering utilities."""

import re
from pathlib import Path
from typing import List, Optional, Set

from src.config import settings
from src.exceptions.custom_exceptions import DiffParsingError
from src.utils.logger import get_logger

logger = get_logger(__name__)


class DiffParser:
    """Parser for Git diffs with smart filtering."""

    def __init__(self):
        self.exclude_patterns: List[str] = settings.EXCLUDE_FILE_PATTERNS
        self.max_file_size: int = settings.MAX_FILE_SIZE_BYTES
        self.max_lines: int = settings.MAX_DIFF_LINES
        self._compiled_patterns: Optional[List[re.Pattern]] = None

    @property
    def compiled_patterns(self) -> List[re.Pattern]:
        """Lazy compile exclusion patterns."""
        if self._compiled_patterns is None:
            self._compiled_patterns = [
                re.compile(pattern.replace("*", ".*")) for pattern in self.exclude_patterns
            ]
        return self._compiled_patterns

    def should_exclude_file(self, filename: str) -> bool:
        """
        Check if a file should be excluded based on patterns.

        Args:
            filename: The file path to check.

        Returns:
            True if the file should be excluded.
        """
        # Check against compiled patterns
        for pattern in self.compiled_patterns:
            if pattern.search(filename):
                logger.debug(f"Excluding file {filename} (matched pattern: {pattern.pattern})")
                return True

        # Check common binary extensions
        binary_extensions = {
            ".png",
            ".jpg",
            ".jpeg",
            ".gif",
            ".ico",
            ".svg",
            ".pdf",
            ".zip",
            ".tar",
            ".gz",
            ".exe",
            ".dll",
            ".so",
            ".dylib",
            ".pyc",
            ".pyo",
            ".class",
            ".jar",
        }

        path = Path(filename)
        if path.suffix.lower() in binary_extensions:
            logger.debug(f"Excluding binary file: {filename}")
            return True

        return False

    def filter_diff(self, diff_content: str) -> str:
        """
        Filter diff content to remove excluded files and limit size.

        Args:
            diff_content: Raw diff string.

        Returns:
            Filtered diff string.

        Raises:
            DiffParsingError: If parsing fails.
        """
        try:
            lines = diff_content.splitlines()
            filtered_lines = []
            current_file = None
            file_has_content = False
            line_count = 0
            file_size = 0

            for line in lines:
                # Detect file headers (diff --git a/... b/...)
                if line.startswith("diff --git"):
                    # If we were tracking a file, check if it should be included
                    if current_file and file_has_content:
                        # Add a separator for readability
                        filtered_lines.append("")
                        filtered_lines.extend(current_file)
                        filtered_lines.append("")

                    # Start new file tracking
                    current_file = []
                    file_has_content = False
                    # Extract filename from diff header
                    match = re.search(r"b/([^\s]+)", line)
                    filename = match.group(1) if match else None

                    if filename and self.should_exclude_file(filename):
                        current_file = None  # Skip this file
                        continue

                    if filename:
                        current_file.append(line)
                    else:
                        current_file = None
                    continue

                # If we're skipping a file, continue
                if current_file is None:
                    continue

                # Add line to current file
                current_file.append(line)
                file_has_content = True

                # Track size
                file_size += len(line)

                # Check file size limit
                if file_size > self.max_file_size:
                    logger.warning(f"File exceeded size limit, truncating: {file_size} bytes")
                    current_file.append("... (diff truncated due to size)")
                    break

                line_count += 1

                # Check total line limit
                if line_count > self.max_lines:
                    logger.warning(f"Diff exceeded line limit ({self.max_lines}), truncating")
                    filtered_lines.append("... (diff truncated due to length)")
                    break

            # Don't forget the last file
            if current_file and file_has_content:
                filtered_lines.extend(current_file)

            # Remove consecutive empty lines
            result = self._clean_empty_lines("\n".join(filtered_lines))

            logger.info(f"Filtered diff: {len(result)} characters, {line_count} lines")
            return result

        except Exception as e:
            raise DiffParsingError(f"Failed to parse diff: {str(e)}")

    @staticmethod
    def _clean_empty_lines(text: str) -> str:
        """Remove consecutive empty lines."""
        return re.sub(r"\n\s*\n+", "\n\n", text)

    def extract_file_changes(self, diff_content: str) -> List[dict]:
        """
        Extract structured file changes from diff.

        Args:
            diff_content: The diff string.

        Returns:
            List of file change dictionaries.
        """
        changes = []
        lines = diff_content.splitlines()
        current_file = None
        additions = 0
        deletions = 0

        for line in lines:
            if line.startswith("diff --git"):
                if current_file:
                    changes.append(
                        {
                            "filename": current_file,
                            "additions": additions,
                            "deletions": deletions,
                            "changes": additions + deletions,
                        }
                    )
                    additions = 0
                    deletions = 0

                match = re.search(r"b/([^\s]+)", line)
                current_file = match.group(1) if match else None

            elif current_file and line.startswith("+"):
                additions += 1
            elif current_file and line.startswith("-"):
                deletions += 1

        # Don't forget the last file
        if current_file:
            changes.append(
                {
                    "filename": current_file,
                    "additions": additions,
                    "deletions": deletions,
                    "changes": additions + deletions,
                }
            )

        return changes


# Singleton instance
diff_parser = DiffParser()