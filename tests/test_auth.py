import base64
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

from google.oauth2.credentials import Credentials
import pytest

from weather_tracker import auth


@pytest.fixture
def client():
    return {"installed": {
        "client_id": "test-client",
        "client_secret": "private-client-secret",
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": "https://oauth2.googleapis.com/token",
        "redirect_uris": [auth.REDIRECT_URI],
    }}


def set_bundle(monkeypatch, client, *, as_string=False):
    bundle = {
        "client_secret.json": json.dumps(client) if as_string else client,
        ".encryption_key": "DO-NOT-READ-KEY",
        "credentials.enc": "DO-NOT-READ-CUBSCOUTS-TOKEN",
        "../../cubscouts.json": "DO-NOT-EXTRACT",
    }
    monkeypatch.setenv("GWS_AUTH", base64.b64encode(json.dumps(bundle).encode()).decode())


@pytest.mark.parametrize("as_string", [False, True])
def test_unpack_roundtrip(monkeypatch, client, capsys, as_string):
    set_bundle(monkeypatch, client, as_string=as_string)
    monkeypatch.setenv("TMPDIR", str(Path.cwd()))
    with auth.unpack_client() as path:
        assert json.loads(path.read_text()) == client
        assert path.name == "client_secret.json"
        assert path.stat().st_mode & 0o777 == 0o600
        assert path.parent.stat().st_mode & 0o777 == 0o700
        assert not path.is_relative_to(Path.cwd())
        assert list(path.parent.iterdir()) == [path]
        assert "GWS_AUTH" not in auth.os.environ
    assert not path.parent.exists()
    assert capsys.readouterr() == ("", "")


@pytest.mark.parametrize("payload", [None, "", "not base64", "e30=", "W10=", "bnVsbA=="])
def test_invalid_bundle(monkeypatch, capsys, payload):
    monkeypatch.delenv("GWS_AUTH", raising=False)
    if payload is not None:
        monkeypatch.setenv("GWS_AUTH", payload)
    with pytest.raises(auth.AuthError, match="valid, nonempty"):
        with auth.unpack_client():
            pytest.fail("invalid bundle accepted")
    assert "GWS_AUTH" not in auth.os.environ
    assert capsys.readouterr() == ("", "")


@pytest.mark.parametrize("bad_client", [None, "", "not JSON", {}, [], {"installed": {}}])
def test_invalid_client(monkeypatch, bad_client):
    set_bundle(monkeypatch, bad_client)
    with pytest.raises(auth.AuthError):
        with auth.unpack_client():
            pytest.fail("invalid client accepted")


def test_empty_client_secret(monkeypatch, client):
    client["installed"]["client_secret"] = " "
    set_bundle(monkeypatch, client)
    with pytest.raises(auth.AuthError):
        with auth.unpack_client():
            pytest.fail("empty client secret accepted")


def test_cleanup_on_caller_error(monkeypatch, client):
    set_bundle(monkeypatch, client)
    with pytest.raises(RuntimeError, match="caller"):
        with auth.unpack_client() as path:
            raise RuntimeError("caller")
    assert not path.exists()


def test_daily_credentials(monkeypatch, client, capsys):
    set_bundle(monkeypatch, client)
    monkeypatch.setenv("SHEETS_REFRESH_TOKEN", "weather-tracker-only-token")
    monkeypatch.setattr(auth.InstalledAppFlow, "from_client_config", Mock(side_effect=AssertionError))
    result = auth.credentials()
    assert isinstance(result, Credentials)
    assert result.refresh_token == "weather-tracker-only-token"
    assert tuple(result.scopes) == auth.SHEETS_SCOPES
    assert result.client_id == client["installed"]["client_id"]
    assert result.client_secret == client["installed"]["client_secret"]
    assert result.token is None
    assert "GWS_AUTH" not in auth.os.environ
    assert capsys.readouterr() == ("", "")


@pytest.mark.parametrize("token", ["", " ", None])
def test_missing_daily_token(monkeypatch, client, token):
    set_bundle(monkeypatch, client)
    monkeypatch.delenv("SHEETS_REFRESH_TOKEN", raising=False)
    if token is not None:
        monkeypatch.setenv("SHEETS_REFRESH_TOKEN", token)
    with pytest.raises(auth.AuthError, match="SHEETS_REFRESH_TOKEN is required"):
        auth.credentials()


@pytest.mark.parametrize("kind, redirects", [
    ("installed", []), ("installed", ["http://localhost:9999/"]),
    ("web", ["http://localhost"]), ("web", ["http://localhost:8080"]),
    ("web", ["http://127.0.0.1:8080/"]), ("web", auth.REDIRECT_URI),
])
def test_redirect_refusal(monkeypatch, client, capsys, kind, redirects):
    info = client["installed"]
    info["redirect_uris"] = redirects
    set_bundle(monkeypatch, {kind: info})
    factory = Mock()
    monkeypatch.setattr(auth.InstalledAppFlow, "from_client_config", factory)
    with pytest.raises(auth.AuthError) as error:
        auth.authorize()
    assert str(error.value) == f"Add this OAuth redirect URI in Google Cloud: {auth.REDIRECT_URI}"
    factory.assert_not_called()
    assert capsys.readouterr() == ("", "")


@pytest.mark.parametrize("kind, redirects", [
    ("installed", ["http://localhost"]),
    ("installed", ["http://localhost/"]),
    ("installed", [auth.REDIRECT_URI]), ("web", [auth.REDIRECT_URI]),
])
def test_authorize_secure_token_and_no_blob_reads(monkeypatch, client, capsys, kind, redirects):
    info = client["installed"]
    info["redirect_uris"] = redirects
    config = {kind: info}
    set_bundle(monkeypatch, config)
    flow = Mock()
    flow.run_local_server.return_value = SimpleNamespace(refresh_token="new-project-refresh-token")
    factory = Mock(return_value=flow)
    monkeypatch.setattr(auth.InstalledAppFlow, "from_client_config", factory)
    original_read = Path.read_text
    reads = []

    def read_client_only(path, *args, **kwargs):
        reads.append(path)
        assert path.name == "client_secret.json"
        return original_read(path, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", read_client_only)
    path = auth.authorize()
    try:
        assert original_read(path) == "new-project-refresh-token"
        assert path.stat().st_mode & 0o777 == 0o600
        assert not path.is_relative_to(Path.cwd())
        assert len(reads) == 1
        assert not reads[0].exists()
        factory.assert_called_once_with(config, scopes=auth.SHEETS_SCOPES)
        arguments = flow.run_local_server.call_args.kwargs
        assert arguments["host"] == "localhost"
        assert arguments["port"] == 8080
        assert arguments["redirect_uri_trailing_slash"] is True
        assert arguments["access_type"] == "offline"
        assert arguments["prompt"] == "consent"
        assert "{url}" not in arguments["authorization_prompt_message"]
        assert capsys.readouterr() == ("", "")
    finally:
        path.unlink()


@pytest.mark.parametrize("failure", ["provider", "no-token"])
def test_consent_failure_is_safe(monkeypatch, client, capsys, failure):
    set_bundle(monkeypatch, client)
    flow = Mock()
    if failure == "provider":
        flow.run_local_server.side_effect = RuntimeError("private-client-secret secret-token")
    else:
        flow.run_local_server.return_value = SimpleNamespace(refresh_token=None)
    monkeypatch.setattr(auth.InstalledAppFlow, "from_client_config", Mock(return_value=flow))
    with pytest.raises(auth.AuthError) as error:
        auth.authorize()
    assert "private-client-secret" not in str(error.value)
    assert "secret-token" not in str(error.value)
    assert error.value.__suppress_context__ or failure == "no-token"
    assert capsys.readouterr() == ("", "")
