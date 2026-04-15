#!/usr/bin/env python3
"""Tests for twin/lib/context.py"""

import tempfile
import shutil
from pathlib import Path

import pytest

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "lib"))

from context import ContextManager


@pytest.fixture
def tmp_context_dir(tmp_path):
    """Create a temporary context directory."""
    ctx_dir = tmp_path / "context"
    ctx_dir.mkdir()
    return ctx_dir


@pytest.fixture
def cm(tmp_context_dir):
    """Create a ContextManager with a temp directory."""
    return ContextManager({"context_dir": str(tmp_context_dir)})


def _sample_session_data(**overrides):
    data = {
        "session_id": "abc123",
        "mode": "work",
        "agent": "technical-lead",
        "planning_discussion": "Discussed API design.",
        "decisions": ["Use REST"],
        "reasoning": "5 Whys applied.",
        "next_steps": ["Write tests"],
        "files_discussed": ["api.py"],
    }
    data.update(overrides)
    return data


class TestContextFilename:
    def test_deterministic(self, cm):
        a = cm.get_context_filename("/foo/bar")
        b = cm.get_context_filename("/foo/bar")
        assert a == b

    def test_different_paths_differ(self, cm):
        a = cm.get_context_filename("/foo")
        b = cm.get_context_filename("/bar")
        assert a != b

    def test_format(self, cm):
        name = cm.get_context_filename("/tmp/test")
        assert name.startswith("context-")
        assert name.endswith(".txt")


class TestAppendAndLoad:
    def test_append_creates_file(self, cm):
        cwd = "/tmp/test_project"
        cm.append_session(cwd, _sample_session_data())
        ctx = cm.load_context(cwd)
        assert ctx is not None
        assert ctx["repository"] == cwd

    def test_append_multiple_sessions(self, cm):
        cwd = "/tmp/test_project"
        cm.append_session(cwd, _sample_session_data(session_id="s1"))
        cm.append_session(cwd, _sample_session_data(session_id="s2"))
        ctx = cm.load_context(cwd)
        assert len(ctx["sessions"]) == 2

    def test_load_nonexistent_returns_none(self, cm):
        assert cm.load_context("/nonexistent") is None


class TestParseContext:
    def test_parses_header(self, cm):
        content = "# Repository: /my/repo\n\n---\n\n"
        result = cm.parse_context(content, "/fallback")
        assert result["repository"] == "/my/repo"

    def test_fallback_repo(self, cm):
        content = "no header here"
        result = cm.parse_context(content, "/fallback")
        assert result["repository"] == "/fallback"


class TestRecentSessions:
    def test_returns_last_n(self, cm):
        cwd = "/tmp/proj"
        for i in range(5):
            cm.append_session(cwd, _sample_session_data(session_id=f"s{i}"))
        recent = cm.get_recent_sessions(cwd, count=2)
        assert len(recent) == 2

    def test_empty_returns_empty(self, cm):
        assert cm.get_recent_sessions("/nope") == []


class TestDeleteSession:
    def test_delete_by_index(self, cm):
        cwd = "/tmp/proj"
        cm.append_session(cwd, _sample_session_data(session_id="s1"))
        cm.append_session(cwd, _sample_session_data(session_id="s2"))
        result = cm.delete_session_by_index(cwd, 1)
        assert result is True
        ctx = cm.load_context(cwd)
        assert len(ctx["sessions"]) == 1

    def test_delete_invalid_index(self, cm):
        cwd = "/tmp/proj"
        cm.append_session(cwd, _sample_session_data())
        assert cm.delete_session_by_index(cwd, 0) is False
        assert cm.delete_session_by_index(cwd, 99) is False

    def test_delete_no_context(self, cm):
        assert cm.delete_session_by_index("/nope", 1) is False


class TestArchive:
    def test_archive_creates_file(self, cm):
        cwd = "/tmp/proj"
        cm.append_session(cwd, _sample_session_data())
        archive_path = cm.archive_context(cwd)
        assert archive_path is not None
        assert archive_path.exists()

    def test_archive_nonexistent_returns_none(self, cm):
        assert cm.archive_context("/nope") is None

    def test_clear_with_archive(self, cm):
        cwd = "/tmp/proj"
        cm.append_session(cwd, _sample_session_data())
        success, archive_path = cm.clear_context_with_archive(cwd)
        assert success is True
        assert archive_path is not None
        assert archive_path.exists()
        assert cm.load_context(cwd) is None


class TestListVerbose:
    def test_verbose_list(self, cm):
        cwd = "/tmp/proj"
        cm.append_session(cwd, _sample_session_data())
        sessions = cm.list_sessions_verbose(cwd)
        assert len(sessions) == 1
        assert sessions[0]["index"] == 1
        assert sessions[0]["mode"] == "work"

    def test_empty_verbose(self, cm):
        assert cm.list_sessions_verbose("/nope") == []


class TestGetContextSummary:
    def test_summary_with_sessions(self, cm):
        cwd = "/tmp/proj"
        cm.append_session(cwd, _sample_session_data())
        summary = cm.get_context_summary(cwd)
        assert "1 previous session" in summary

    def test_summary_no_context(self, cm):
        summary = cm.get_context_summary("/nope")
        assert "No previous context" in summary
