"""Tests for authentication functions. All external calls are mocked."""

import os

from unittest.mock import MagicMock, patch, call

import stream


# ── _build_credentials_from_env ─────────────────────────────────────────────


class TestBuildCredentialsFromEnv:
    @patch("stream.Credentials")
    def test_build_credentials_from_env(self, mock_creds_cls, monkeypatch):
        """Constructs Credentials with values from env and config."""
        monkeypatch.setenv("GOOGLE_ACCESS_TOKEN", "at-123")
        monkeypatch.setenv("GOOGLE_REFRESH_TOKEN", "rt-456")
        monkeypatch.setenv("GOOGLE_CLIENT_SECRET", "cs-789")

        config = {"google": {"clientId": "cid"}}
        stream._build_credentials_from_env(config)

        mock_creds_cls.assert_called_once_with(
            token="at-123",
            refresh_token="rt-456",
            token_uri="https://oauth2.googleapis.com/token",
            client_id="cid",
            client_secret="cs-789",
            scopes=stream.SCOPES,
        )

    @patch("stream.Credentials")
    def test_build_credentials_missing_env(self, mock_creds_cls, monkeypatch):
        """With no env vars set, empty strings are used."""
        monkeypatch.delenv("GOOGLE_ACCESS_TOKEN", raising=False)
        monkeypatch.delenv("GOOGLE_REFRESH_TOKEN", raising=False)
        monkeypatch.delenv("GOOGLE_CLIENT_SECRET", raising=False)

        config = {"google": {"clientId": "cid"}}
        stream._build_credentials_from_env(config)

        mock_creds_cls.assert_called_once_with(
            token="",
            refresh_token="",
            token_uri="https://oauth2.googleapis.com/token",
            client_id="cid",
            client_secret="",
            scopes=stream.SCOPES,
        )


# ── _refresh_credentials ───────────────────────────────────────────────────


class TestRefreshCredentials:
    @patch("stream.save_env_value")
    @patch("stream.GoogleAuthRequest")
    def test_refresh_credentials_success(self, mock_auth_req, mock_save, mock_logger):
        """Successful refresh returns True and saves the access token."""
        creds = MagicMock()
        creds.token = "new-token"
        creds.refresh_token = "new-refresh"

        result = stream._refresh_credentials(creds, mock_logger)

        assert result is True
        creds.refresh.assert_called_once()
        mock_save.assert_any_call("GOOGLE_ACCESS_TOKEN", "new-token")

    @patch("stream.save_env_value")
    @patch("stream.GoogleAuthRequest")
    def test_refresh_credentials_saves_refresh_token(
        self, mock_auth_req, mock_save, mock_logger
    ):
        """When creds.refresh_token is set after refresh, it is persisted."""
        creds = MagicMock()
        creds.token = "new-token"
        creds.refresh_token = "new-refresh"

        stream._refresh_credentials(creds, mock_logger)

        mock_save.assert_any_call("GOOGLE_REFRESH_TOKEN", "new-refresh")

    @patch("stream.save_env_value")
    @patch("stream.GoogleAuthRequest")
    def test_refresh_credentials_no_new_refresh(
        self, mock_auth_req, mock_save, mock_logger
    ):
        """When creds.refresh_token is None after refresh, only access token is saved."""
        creds = MagicMock()
        creds.token = "new-token"
        creds.refresh_token = None

        stream._refresh_credentials(creds, mock_logger)

        # Access token should be saved
        mock_save.assert_any_call("GOOGLE_ACCESS_TOKEN", "new-token")
        # Refresh token should NOT be saved
        for c in mock_save.call_args_list:
            assert c != call("GOOGLE_REFRESH_TOKEN", None)

    @patch("stream.save_env_value")
    @patch("stream.GoogleAuthRequest")
    def test_refresh_credentials_failure(self, mock_auth_req, mock_save, mock_logger):
        """When refresh() raises, returns False and logs a warning."""
        creds = MagicMock()
        creds.refresh.side_effect = Exception("network error")

        result = stream._refresh_credentials(creds, mock_logger)

        assert result is False
        mock_logger.warn.assert_called_once()


# ── _reauthenticate ────────────────────────────────────────────────────────


class TestReauthenticate:
    @patch("stream.save_env_value")
    @patch("stream.run_oauth_flow")
    def test_reauthenticate_calls_oauth(
        self, mock_oauth, mock_save, monkeypatch, mock_logger
    ):
        """_reauthenticate invokes run_oauth_flow with client_id and secret."""
        monkeypatch.setenv("GOOGLE_CLIENT_SECRET", "sec-123")
        mock_creds = MagicMock()
        mock_creds.token = "tok"
        mock_creds.refresh_token = "ref"
        mock_oauth.return_value = mock_creds

        config = {"google": {"clientId": "cid-456"}}
        stream._reauthenticate(config, mock_logger)

        mock_oauth.assert_called_once_with("cid-456", "sec-123")

    @patch("stream.save_env_value")
    @patch("stream.run_oauth_flow")
    def test_reauthenticate_saves_tokens(
        self, mock_oauth, mock_save, monkeypatch, mock_logger
    ):
        """_reauthenticate persists both access and refresh tokens."""
        monkeypatch.setenv("GOOGLE_CLIENT_SECRET", "sec")
        mock_creds = MagicMock()
        mock_creds.token = "access-tok"
        mock_creds.refresh_token = "refresh-tok"
        mock_oauth.return_value = mock_creds

        config = {"google": {"clientId": "cid"}}
        stream._reauthenticate(config, mock_logger)

        mock_save.assert_any_call("GOOGLE_ACCESS_TOKEN", "access-tok")
        mock_save.assert_any_call("GOOGLE_REFRESH_TOKEN", "refresh-tok")


# ── get_valid_credentials ──────────────────────────────────────────────────


class TestGetValidCredentials:
    @patch("stream._reauthenticate")
    @patch("stream.load_env")
    def test_get_valid_credentials_no_refresh_token(
        self, mock_load_env, mock_reauth, monkeypatch, mock_logger, sample_config
    ):
        """When GOOGLE_REFRESH_TOKEN is empty, _reauthenticate is called."""
        monkeypatch.setenv("GOOGLE_REFRESH_TOKEN", "")
        mock_reauth.return_value = MagicMock()

        stream.get_valid_credentials(sample_config, mock_logger)

        mock_reauth.assert_called_once_with(sample_config, mock_logger)

    @patch("stream._build_credentials_from_env")
    @patch("stream.load_env")
    def test_get_valid_credentials_valid_token(
        self, mock_load_env, mock_build, monkeypatch, mock_logger, sample_config
    ):
        """When the existing token is valid, it is returned immediately."""
        monkeypatch.setenv("GOOGLE_REFRESH_TOKEN", "rt-ok")
        creds = MagicMock()
        creds.valid = True
        mock_build.return_value = creds

        result = stream.get_valid_credentials(sample_config, mock_logger)

        assert result is creds

    @patch("stream._refresh_credentials")
    @patch("stream._build_credentials_from_env")
    @patch("stream.load_env")
    def test_get_valid_credentials_refresh_succeeds(
        self,
        mock_load_env,
        mock_build,
        mock_refresh,
        monkeypatch,
        mock_logger,
        sample_config,
    ):
        """When the token is invalid but refresh succeeds, creds are returned."""
        monkeypatch.setenv("GOOGLE_REFRESH_TOKEN", "rt-ok")
        creds = MagicMock()
        creds.valid = False
        mock_build.return_value = creds
        mock_refresh.return_value = True

        result = stream.get_valid_credentials(sample_config, mock_logger)

        assert result is creds
        mock_refresh.assert_called_once_with(creds, mock_logger)

    @patch("stream._reauthenticate")
    @patch("stream._refresh_credentials")
    @patch("stream._build_credentials_from_env")
    @patch("stream.load_env")
    def test_get_valid_credentials_refresh_fails_reauthenticates(
        self,
        mock_load_env,
        mock_build,
        mock_refresh,
        mock_reauth,
        monkeypatch,
        mock_logger,
        sample_config,
    ):
        """When refresh fails, _reauthenticate is called as fallback."""
        monkeypatch.setenv("GOOGLE_REFRESH_TOKEN", "rt-ok")
        creds = MagicMock()
        creds.valid = False
        mock_build.return_value = creds
        mock_refresh.return_value = False
        mock_reauth.return_value = MagicMock()

        stream.get_valid_credentials(sample_config, mock_logger)

        mock_reauth.assert_called_once_with(sample_config, mock_logger)


# ── build_youtube_service ──────────────────────────────────────────────────


class TestBuildYoutubeService:
    @patch("stream.build_service")
    def test_build_youtube_service(self, mock_build):
        """build_youtube_service delegates to build_service with correct args."""
        creds = MagicMock()
        stream.build_youtube_service(creds)

        mock_build.assert_called_once_with("youtube", "v3", credentials=creds)


# ── run_oauth_flow ─────────────────────────────────────────────────────────


class TestRunOAuthFlow:
    @patch("stream.InstalledAppFlow")
    def test_run_oauth_flow_calls_installed_app_flow(self, mock_flow_cls):
        """run_oauth_flow builds a flow from client config and runs it."""
        mock_flow = MagicMock()
        mock_flow_cls.from_client_config.return_value = mock_flow

        stream.run_oauth_flow("my-client-id", "my-secret")

        mock_flow_cls.from_client_config.assert_called_once()
        args, kwargs = mock_flow_cls.from_client_config.call_args
        # First arg is the client config dict, second is scopes
        assert args[0]["installed"]["client_id"] == "my-client-id"
        assert args[0]["installed"]["client_secret"] == "my-secret"
        assert args[1] == stream.SCOPES
        mock_flow.run_local_server.assert_called_once_with(port=0, prompt="select_account")
