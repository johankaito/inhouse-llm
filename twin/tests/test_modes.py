#!/usr/bin/env python3
"""Unit tests for twin/lib/modes.py"""

import sys
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock
from datetime import datetime

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "lib"))

from modes import ModeDetector


def _default_config():
    return {
        "mode_config": {
            "work_patterns": ["/work/", "/projects/corp/"],
            "personal_patterns": ["/personal/", "/side-projects/"],
            "work_emails": ["@corp.com"],
            "work_hours": {
                "days": [0, 1, 2, 3, 4],
                "start": 9,
                "end": 18,
            },
        }
    }


class TestDirectoryPatterns(unittest.TestCase):
    def test_work_pattern_matches(self):
        det = ModeDetector(_default_config())
        self.assertEqual(det._check_directory_patterns("/home/user/work/repo"), "work")

    def test_personal_pattern_matches(self):
        det = ModeDetector(_default_config())
        self.assertEqual(det._check_directory_patterns("/home/user/personal/stuff"), "personal")

    def test_no_match_returns_none(self):
        det = ModeDetector(_default_config())
        self.assertIsNone(det._check_directory_patterns("/home/user/random"))


class TestGitEmail(unittest.TestCase):
    @patch("modes.subprocess.run")
    def test_work_email_detected(self, mock_run):
        mock_run.return_value = MagicMock(
            returncode=0, stdout="dev@corp.com\n"
        )
        det = ModeDetector(_default_config())
        self.assertEqual(det._check_git_email("/some/path"), "work")

    @patch("modes.subprocess.run")
    def test_personal_email_detected(self, mock_run):
        mock_run.return_value = MagicMock(
            returncode=0, stdout="me@gmail.com\n"
        )
        det = ModeDetector(_default_config())
        self.assertEqual(det._check_git_email("/some/path"), "personal")

    @patch("modes.subprocess.run", side_effect=FileNotFoundError)
    def test_git_not_installed(self, mock_run):
        det = ModeDetector(_default_config())
        self.assertIsNone(det._check_git_email("/some/path"))

    @patch("modes.subprocess.run")
    def test_git_returns_nonzero(self, mock_run):
        mock_run.return_value = MagicMock(returncode=128, stdout="")
        det = ModeDetector(_default_config())
        self.assertIsNone(det._check_git_email("/some/path"))


class TestWorkHours(unittest.TestCase):
    @patch("modes.datetime")
    def test_during_work_hours(self, mock_dt):
        mock_now = MagicMock()
        mock_now.weekday.return_value = 2  # Wednesday
        mock_now.hour = 14
        mock_dt.now.return_value = mock_now
        det = ModeDetector(_default_config())
        self.assertTrue(det._is_work_hours())

    @patch("modes.datetime")
    def test_outside_work_hours(self, mock_dt):
        mock_now = MagicMock()
        mock_now.weekday.return_value = 2  # Wednesday
        mock_now.hour = 22
        mock_dt.now.return_value = mock_now
        det = ModeDetector(_default_config())
        self.assertFalse(det._is_work_hours())

    @patch("modes.datetime")
    def test_weekend(self, mock_dt):
        mock_now = MagicMock()
        mock_now.weekday.return_value = 5  # Saturday
        mock_now.hour = 14
        mock_dt.now.return_value = mock_now
        det = ModeDetector(_default_config())
        self.assertFalse(det._is_work_hours())


class TestDetectPriorityLadder(unittest.TestCase):
    """Test that detect() follows the priority ladder correctly."""

    @patch("modes.ModeDetector._load_local_settings", return_value={"mode": "work"})
    def test_local_settings_override_everything(self, _mock):
        det = ModeDetector(_default_config())
        # Even in a personal-pattern dir, local settings win
        self.assertEqual(det.detect("/home/user/personal/repo"), "work")

    @patch("modes.ModeDetector._load_local_settings", return_value={})
    def test_directory_pattern_beats_git_email(self, _mock):
        det = ModeDetector(_default_config())
        self.assertEqual(det.detect("/home/user/work/repo"), "work")

    @patch("modes.ModeDetector._load_local_settings", return_value={})
    @patch("modes.ModeDetector._check_git_email", return_value="work")
    @patch("modes.ModeDetector._is_work_hours", return_value=False)
    def test_git_email_used_when_no_dir_match(self, _wh, _ge, _ls):
        det = ModeDetector(_default_config())
        self.assertEqual(det.detect("/home/user/random"), "work")

    @patch("modes.ModeDetector._load_local_settings", return_value={})
    @patch("modes.ModeDetector._check_git_email", return_value=None)
    @patch("modes.ModeDetector._is_work_hours", return_value=False)
    def test_defaults_to_personal(self, _wh, _ge, _ls):
        det = ModeDetector(_default_config())
        self.assertEqual(det.detect("/home/user/random"), "personal")


if __name__ == "__main__":
    unittest.main()
