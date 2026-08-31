"""Unit tests for diff parser."""

import pytest

from src.utils.diff_parser import diff_parser


class TestDiffParser:
    """Test suite for DiffParser."""

    def test_should_exclude_file_patterns(self):
        """Test file exclusion patterns."""
        # Should exclude
        assert diff_parser.should_exclude_file("package-lock.json") is True
        assert diff_parser.should_exclude_file("yarn.lock") is True
        assert diff_parser.should_exclude_file("file.min.js") is True
        assert diff_parser.should_exclude_file("file.min.css") is True
        assert diff_parser.should_exclude_file("dist/bundle.min.js") is True

        # Should include
        assert diff_parser.should_exclude_file("app.py") is False
        assert diff_parser.should_exclude_file("src/controller.py") is False
        assert diff_parser.should_exclude_file("README.md") is False

    def test_should_exclude_binary_files(self):
        """Test binary file exclusion."""
        assert diff_parser.should_exclude_file("image.png") is True
        assert diff_parser.should_exclude_file("file.pdf") is True
        assert diff_parser.should_exclude_file("app.jar") is True
        assert diff_parser.should_exclude_file("script.py") is False

    def test_filter_diff_basic(self):
        """Test basic diff filtering."""
        diff = """diff --git a/file.py b/file.py
index abc..def 100644
--- a/file.py
+++ b/file.py
@@ -1,3 +1,4 @@
 print('hello')
+print('world')
 print('goodbye')
 """
        filtered = diff_parser.filter_diff(diff)
        assert "file.py" in filtered
        assert "+print('world')" in filtered
        assert len(filtered) > 0

    def test_filter_diff_excludes_large_files(self):
        """Test diff filtering excludes large files."""
        # Create a large diff that exceeds limits
        diff_lines = ["diff --git a/large.py b/large.py"]
        for i in range(2000):  # Exceeds max_lines
            diff_lines.append(f"+line{i}")
        diff = "\n".join(diff_lines)

        filtered = diff_parser.filter_diff(diff)
        assert len(filtered) < len(diff)
        assert "truncated" in filtered or len(filtered) < len(diff)

    def test_filter_diff_excludes_pattern_matches(self):
        """Test diff filtering excludes pattern matches."""
        diff = """diff --git a/package-lock.json b/package-lock.json
index abc..def 100644
--- a/package-lock.json
+++ b/package-lock.json
@@ -1,3 +1,4 @@
{
  "name": "test"
}
"""
        filtered = diff_parser.filter_diff(diff)
        assert "package-lock.json" not in filtered
        assert filtered.strip() == ""

    def test_extract_file_changes(self):
        """Test extracting file changes from diff."""
        diff = """diff --git a/file1.py b/file1.py
+++ b/file1.py
+print('hello')
+print('world')
--- b/file1.py
-print('old')
diff --git a/file2.py b/file2.py
+++ b/file2.py
+print('new')
"""
        changes = diff_parser.extract_file_changes(diff)
        assert len(changes) == 2
        assert changes[0]["filename"] == "file1.py"
        assert changes[0]["additions"] == 2
        assert changes[0]["deletions"] == 1
        assert changes[1]["filename"] == "file2.py"
        assert changes[1]["additions"] == 1

    def test_clean_empty_lines(self):
        """Test cleaning empty lines."""
        text = "line1\n\n\nline2\n\nline3"
        cleaned = diff_parser._clean_empty_lines(text)
        assert cleaned == "line1\n\nline2\n\nline3"