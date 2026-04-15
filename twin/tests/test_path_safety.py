#!/usr/bin/env python3
"""Tests for sensitive-path guardrails in tools.py"""

import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

# Ensure twin/lib is on path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'lib'))

from tools import ToolRegistry, ToolResult


@pytest.fixture
def registry(tmp_path):
    """Create a ToolRegistry with cwd set to tmp_path."""
    orig = os.getcwd()
    os.chdir(tmp_path)
    try:
        reg = ToolRegistry(config={})
        yield reg
    finally:
        os.chdir(orig)


class TestWriteFileGuardrails:
    """Verify _write_file blocks sensitive paths."""

    def test_write_inside_cwd_succeeds(self, registry, tmp_path):
        target = str(tmp_path / 'safe_file.txt')
        result = registry._write_file(target, 'hello')
        assert result.success is True
        assert Path(target).read_text() == 'hello'

    def test_write_traversal_blocked(self, registry, tmp_path):
        target = str(tmp_path / '../../etc/shadow')
        result = registry._write_file(target, 'evil')
        assert result.success is False
        assert 'blocked' in (result.error or '').lower() or 'escapes' in (result.error or '').lower()

    def test_write_ssh_dir_blocked(self, registry):
        target = os.path.expanduser('~/.ssh/authorized_keys')
        result = registry._write_file(target, 'evil')
        assert result.success is False

    def test_write_etc_blocked(self, registry):
        result = registry._write_file('/etc/passwd', 'evil')
        assert result.success is False

    def test_write_env_file_blocked(self, registry, tmp_path):
        target = str(tmp_path / '.env')
        result = registry._write_file(target, 'SECRET=x')
        assert result.success is False


class TestEditFileGuardrails:
    """Verify _edit_file blocks sensitive paths."""

    def test_edit_traversal_blocked(self, registry, tmp_path):
        target = str(tmp_path / '../../etc/hosts')
        result = registry._edit_file(target, 'old', 'new')
        assert result.success is False

    def test_edit_inside_cwd_allowed(self, registry, tmp_path):
        target = tmp_path / 'editable.txt'
        target.write_text('old content')
        result = registry._edit_file(str(target), 'old content', 'new content')
        assert result.success is True


class TestSelfImproverConfinement:
    """Verify self_improver rejects path-traversal file keys."""

    def test_traversal_in_files_dict(self, tmp_path):
        from self_improver import SelfImprover
        si = SelfImprover(tmp_path)
        # Create a git repo so can_improve passes
        os.system(f'cd {tmp_path} && git init && git commit --allow-empty -m init')

        with pytest.raises(Exception, match='confinement'):
            si.propose_improvement(
                description='test',
                reasoning='test',
                files={'../../etc/evil': 'payload'}
            )
