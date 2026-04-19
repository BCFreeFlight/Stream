"""Tests for the dependency bootstrap (_pip_install)."""

import subprocess
import sys
from unittest.mock import patch

import stream


class TestPipInstall:
    def test_plain_install_is_tried_first(self):
        """_pip_install starts with a plain pip install (no scope flags)."""
        with patch("subprocess.check_call") as mock_call:
            stream._pip_install(["requests"])

        mock_call.assert_called_once_with(
            [sys.executable, "-m", "pip", "install", "requests"]
        )

    def test_passes_all_packages(self):
        """All packages in the list are forwarded to pip in order."""
        with patch("subprocess.check_call") as mock_call:
            stream._pip_install(["pkg-a", "pkg-b", "pkg-c"])

        args = mock_call.call_args[0][0]
        assert args[-3:] == ["pkg-a", "pkg-b", "pkg-c"]

    def test_falls_back_to_user_break_system_packages(self):
        """On PEP 668 failure, retries with --user --break-system-packages."""
        first_error = subprocess.CalledProcessError(1, "pip")
        with patch("subprocess.check_call", side_effect=[first_error, None]) as mock_call, \
             patch("site.getusersitepackages", return_value="/tmp/fake-user-site"), \
             patch("site.addsitedir"):
            stream._pip_install(["requests"])

        assert mock_call.call_count == 2
        first_args = mock_call.call_args_list[0][0][0]
        second_args = mock_call.call_args_list[1][0][0]
        assert "--user" not in first_args
        assert "--break-system-packages" not in first_args
        assert "--user" in second_args
        assert "--break-system-packages" in second_args
        assert second_args[-1] == "requests"

    def test_fallback_adds_user_site_to_sys_path(self):
        """After a fallback install, the user site is added to sys.path."""
        err = subprocess.CalledProcessError(1, "pip")
        fake_site = "/tmp/fake-user-site"
        with patch("subprocess.check_call", side_effect=[err, None]), \
             patch("site.getusersitepackages", return_value=fake_site), \
             patch("site.addsitedir") as mock_addsitedir, \
             patch.object(sys, "path", list(sys.path)):
            stream._pip_install(["requests"])

        mock_addsitedir.assert_called_once_with(fake_site)

    def test_fallback_skips_addsitedir_when_already_on_path(self):
        """If the user site is already on sys.path, addsitedir is not called again."""
        err = subprocess.CalledProcessError(1, "pip")
        fake_site = "/tmp/already-on-path"
        with patch("subprocess.check_call", side_effect=[err, None]), \
             patch("site.getusersitepackages", return_value=fake_site), \
             patch("site.addsitedir") as mock_addsitedir, \
             patch.object(sys, "path", list(sys.path) + [fake_site]):
            stream._pip_install(["requests"])

        mock_addsitedir.assert_not_called()

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
