"""Tests for _prompt, _make_validator, _smart_prompt, and _show_guide."""

from unittest.mock import MagicMock, patch

import stream


# ── _prompt ─────────────────────────────────────────────────────────────────


class TestPrompt:
    def test_prompt_returns_input(self):
        """_prompt returns the value typed by the user."""
        with patch("builtins.input", return_value="hello"):
            result = stream._prompt("Label")
        assert result == "hello"

    def test_prompt_with_default_empty_input(self):
        """When user presses Enter on an empty prompt, the default is returned."""
        with patch("builtins.input", return_value=""):
            result = stream._prompt("Label", default="def")
        assert result == "def"

    def test_prompt_required_re_prompts(self, capsys):
        """A required field with no default re-prompts until a value is given."""
        with patch("builtins.input", side_effect=["", "val"]):
            result = stream._prompt("Label")
        assert result == "val"
        captured = capsys.readouterr()
        assert "required" in captured.out.lower()

    def test_prompt_with_validator_pass(self):
        """When the validator returns True the value is accepted immediately."""
        validator = lambda v: True
        with patch("builtins.input", return_value="good"):
            result = stream._prompt("Label", validator=validator)
        assert result == "good"

    def test_prompt_with_validator_fail_then_pass(self):
        """When the validator fails first, _prompt re-prompts until it passes."""
        call_count = {"n": 0}

        def validator(value):
            call_count["n"] += 1
            return call_count["n"] > 1

        with patch("builtins.input", side_effect=["bad", "good"]):
            result = stream._prompt("Label", validator=validator)
        assert result == "good"


# ── _make_validator ─────────────────────────────────────────────────────────


class TestMakeValidator:
    def test_make_validator_pass(self):
        """Validator returns True when the check function passes."""
        validator = stream._make_validator(lambda v: v == "ok", "bad")
        assert validator("ok") is True

    def test_make_validator_fail(self, capsys):
        """Validator returns False and prints the error message on failure."""
        validator = stream._make_validator(lambda v: v == "ok", "bad input")
        result = validator("nope")
        assert result is False
        captured = capsys.readouterr()
        assert "bad input" in captured.out


# ── _smart_prompt ───────────────────────────────────────────────────────────


class TestSmartPrompt:
    def test_smart_prompt_skips_existing(self):
        """When current value is non-empty, it is returned without calling input."""
        with patch("builtins.input") as mock_input:
            result = stream._smart_prompt("label", "existing_value")
        assert result == "existing_value"
        mock_input.assert_not_called()

    def test_smart_prompt_empty_prompts(self):
        """When current is empty, _smart_prompt delegates to _prompt with default."""
        with patch("builtins.input", return_value=""):
            result = stream._smart_prompt("label", "", default="def")
        assert result == "def"

    def test_smart_prompt_shows_guide(self, capsys):
        """When a guide is provided and current is empty, the guide lines are printed."""
        with patch("builtins.input", return_value="val"):
            result = stream._smart_prompt("label", "", guide=["line1", "line2"])
        assert result == "val"
        captured = capsys.readouterr()
        assert "line1" in captured.out
        assert "line2" in captured.out


# ── _show_guide ─────────────────────────────────────────────────────────────


class TestShowGuide:
    def test_show_guide_prints_lines(self, capsys):
        """All guide lines are printed to stdout."""
        stream._show_guide(["a", "b", "c"])
        captured = capsys.readouterr()
        assert "a" in captured.out
        assert "b" in captured.out
        assert "c" in captured.out
