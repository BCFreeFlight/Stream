"""Tests for the dependency bootstrap (_pip_install)."""

import importlib
import subprocess
import sys
from unittest.mock import patch

import pytest
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

    def test_invalidate_caches_called_when_package_installed(self):
        """importlib.invalidate_caches() is called exactly once after _pip_install."""
        with patch("stream._can_import", return_value=False), \
             patch("stream._pip_install") as mock_pip, \
             patch("importlib.invalidate_caches") as mock_invalidate:
            stream._ensure_dependencies()

        mock_pip.assert_called_once()
        mock_invalidate.assert_called_once()

    def test_invalidate_caches_not_called_when_no_missing_packages(self):
        """invalidate_caches is NOT called when all packages are already present."""
        with patch("stream._can_import", return_value=True), \
             patch("stream._pip_install") as mock_pip, \
             patch("importlib.invalidate_caches") as mock_invalidate:
            stream._ensure_dependencies()

        mock_pip.assert_not_called()
        mock_invalidate.assert_not_called()

    def test_invalidate_caches_called_once_with_multiple_missing(self):
        """invalidate_caches is called exactly once even when multiple packages are installed."""
        with patch("stream._can_import", side_effect=lambda n: False if n in ("requests", "dotenv") else True), \
             patch("stream._pip_install") as mock_pip, \
             patch("importlib.invalidate_caches") as mock_invalidate:
            stream._ensure_dependencies()

        # _pip_install should have been called with both missing packages
        assert mock_pip.call_count == 1
        call_args = mock_pip.call_args[0][0]
        assert "requests" in call_args and "python-dotenv" in call_args
        # invalidate_caches should be called exactly once, not per-package
        mock_invalidate.assert_called_once()

    def test_invalidate_caches_after_install(self):
        """invalidate_caches is called after _pip_install completes, not before."""
        order = []

        def track_pip(*args, **kwargs):
            order.append("pip_install")

        with patch("stream._can_import", return_value=False), \
             patch("stream._pip_install", side_effect=track_pip), \
             patch("importlib.invalidate_caches") as mock_invalidate:

            def track_invalidate():
                order.append("invalidate_caches")

            mock_invalidate.side_effect = track_invalidate
            stream._ensure_dependencies()

        assert order == ["pip_install", "invalidate_caches"]

    def test_tomli_fallback_when_tomllib_unavailable(self):
        """stream.tomllib resolves to tomli when tomllib is not available (Python < 3.11)."""
        # Remove stream and tomllib from sys.modules so we get a fresh import
        for mod in list(sys.modules.keys()):
            if mod == "stream" or mod.startswith("stream."):
                del sys.modules[mod]

        import tomli as _tomli_module  # keep a reference before patching
        real_import = __import__

        def fake_import(name, *args, **kwargs):
            if name == "tomllib":
                raise ModuleNotFoundError(
                    f"No module named '{name}'"
                )
            return real_import(name, *args, **kwargs)

        with patch("builtins.__import__", side_effect=fake_import):
            # Also remove tomllib from sys.modules so the try block actually fails
            if "tomllib" in sys.modules:
                del sys.modules["tomllib"]
            import stream as fresh_stream

        assert fresh_stream.tomllib is _tomli_module
        assert fresh_stream.tomllib.__name__ == "tomli"

    def test_tomllib_used_when_available(self):
        """stream.tomllib resolves to tomllib on Python >= 3.11 (no fallback triggered)."""
        assert stream.tomllib.__name__ == "tomllib"

    def test_module_not_found_when_neither_available(self):
        """ModuleNotFoundError propagates when both tomllib and tomli are unavailable."""
        for mod in list(sys.modules.keys()):
            if mod == "stream" or mod.startswith("stream."):
                del sys.modules[mod]

        real_import = __import__

        def fake_import_both_missing(name, *args, **kwargs):
            if name in ("tomllib", "tomli"):
                raise ModuleNotFoundError(
                    f"No module named '{name}'"
                )
            return real_import(name, *args, **kwargs)

        with patch("builtins.__import__", side_effect=fake_import_both_missing):
            if "tomllib" in sys.modules:
                del sys.modules["tomllib"]
            if "tomli" in sys.modules:
                del sys.modules["tomli"]
            with pytest.raises(ModuleNotFoundError):
                import stream as broken_stream  # noqa: F401

        # Restore normal imports by re-importing stream
        import stream as restored_stream  # noqa: F401
