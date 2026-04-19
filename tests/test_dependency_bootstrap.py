"""Tests for the dependency bootstrap (_pip_install)."""

import subprocess
import sys
from unittest.mock import patch

import stream


class TestPipInstall:
    def test_uses_user_flag_by_default(self):
        """_pip_install invokes pip with --user to avoid system-wide writes."""
        with patch("subprocess.check_call") as mock_call:
            stream._pip_install(["requests"])

        mock_call.assert_called_once_with(
            [sys.executable, "-m", "pip", "install", "--user", "requests"]
        )

    def test_passes_all_packages(self):
        """All packages in the list are forwarded to pip in order."""
        with patch("subprocess.check_call") as mock_call:
            stream._pip_install(["pkg-a", "pkg-b", "pkg-c"])

        args = mock_call.call_args[0][0]
        assert args[-3:] == ["pkg-a", "pkg-b", "pkg-c"]

    def test_falls_back_to_break_system_packages(self):
        """When --user install fails (PEP 668), retries with --break-system-packages."""
        first_error = subprocess.CalledProcessError(1, "pip")
        with patch("subprocess.check_call", side_effect=[first_error, None]) as mock_call:
            stream._pip_install(["requests"])

        assert mock_call.call_count == 2
        first_args = mock_call.call_args_list[0][0][0]
        second_args = mock_call.call_args_list[1][0][0]
        assert "--break-system-packages" not in first_args
        assert "--break-system-packages" in second_args
        assert "--user" in second_args
        assert second_args[-1] == "requests"

    def test_fallback_failure_propagates(self):
        """If the fallback also fails, the exception is raised to the caller."""
        err = subprocess.CalledProcessError(1, "pip")
        with patch("subprocess.check_call", side_effect=[err, err]):
            try:
                stream._pip_install(["requests"])
            except subprocess.CalledProcessError:
                pass
            else:
                raise AssertionError("Expected CalledProcessError to propagate")
