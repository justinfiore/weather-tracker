"""Sheets-only OAuth, without reusing another project's stored credentials."""

import base64
from contextlib import contextmanager
import json
import os
from pathlib import Path
import tempfile
from collections.abc import Iterator

from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow


SHEETS_SCOPES = ("https://www.googleapis.com/auth/spreadsheets",)
REDIRECT_URI = "http://localhost:8080/"


class AuthError(RuntimeError):
    """An operator-safe error; never includes provider exception text."""


def _client_info(config: object) -> tuple[str, dict]:
    if not isinstance(config, dict):
        raise ValueError
    kinds = [kind for kind in ("installed", "web") if kind in config]
    if len(kinds) != 1:
        raise ValueError
    kind = kinds[0]
    info = config[kind]
    if not isinstance(info, dict) or any(
        not isinstance(info.get(key), str) or not info[key].strip()
        for key in ("client_id", "client_secret", "auth_uri", "token_uri")
    ):
        raise ValueError
    return kind, info


@contextmanager
def unpack_client() -> Iterator[Path]:
    """Pop GWS_AUTH and yield a temporary, mode-0600 client_secret.json.

    Only that filename is extracted. All other entries (including encryption
    keys and credential blobs) are ignored. The file is removed on context exit.
    A fixed system temporary root avoids a repo-local TMPDIR.
    """
    payload = os.environ.pop("GWS_AUTH", None)
    try:
        if not payload or not payload.strip():
            raise ValueError
        bundle = json.loads(base64.b64decode(payload, validate=True))
        if not isinstance(bundle, dict):
            raise ValueError
        config = bundle["client_secret.json"]
        if isinstance(config, str):
            config = json.loads(config)
        _client_info(config)
        serialized = json.dumps(config)
    except Exception:
        raise AuthError("GWS_AUTH must contain a valid, nonempty OAuth client_secret.json.") from None
    finally:
        payload = None

    with tempfile.TemporaryDirectory(prefix="weather-tracker-client-", dir="/tmp") as directory:
        path = Path(directory) / "client_secret.json"
        try:
            with open(path, "x", opener=lambda name, flags: os.open(name, flags, 0o600)) as stream:
                os.fchmod(stream.fileno(), 0o600)
                stream.write(serialized)
        except Exception:
            raise AuthError("Could not create the temporary OAuth client file.") from None
        yield path


def credentials() -> Credentials:
    """Build unattended Sheets credentials from GWS_AUTH and SHEETS_REFRESH_TOKEN.

    Does not open a browser or contact Google. Google's API client refreshes the
    access token when needed. GWS_AUTH is consumed even if the token is missing.
    """
    with unpack_client() as path:
        try:
            _, info = _client_info(json.loads(path.read_text()))
            token = os.environ.get("SHEETS_REFRESH_TOKEN")
            if not token or not token.strip():
                raise AuthError("SHEETS_REFRESH_TOKEN is required; run auth as the sheet owner.")
            return Credentials(
                token=None,
                refresh_token=token,
                token_uri=info["token_uri"],
                client_id=info["client_id"],
                client_secret=info["client_secret"],
                scopes=SHEETS_SCOPES,
            )
        except AuthError:
            raise
        except Exception:
            raise AuthError("Could not build Sheets credentials.") from None


def authorize() -> Path:
    """Run interactive consent and return a mode-0600 refresh-token file.

    Consent uses http://localhost:8080/ and Sheets scope only. The returned
    file contains the raw token (no newline), outside the repo. The operator
    must import it as SHEETS_REFRESH_TOKEN with project secret tooling, then
    delete it. Neither the token nor provider exception messages are printed.
    """
    with unpack_client() as path:
        try:
            config = json.loads(path.read_text())
            kind, info = _client_info(config)
            redirects = info.get("redirect_uris", [])
            allowed = isinstance(redirects, list) and (
                REDIRECT_URI in redirects
                or (kind == "installed" and any(
                    uri in redirects for uri in ("http://localhost", "http://localhost/")
                ))
            )
            if not allowed:
                raise AuthError(f"Add this OAuth redirect URI in Google Cloud: {REDIRECT_URI}")
            flow = InstalledAppFlow.from_client_config(config, scopes=SHEETS_SCOPES)
            result = flow.run_local_server(
                host="localhost",
                port=8080,
                redirect_uri_trailing_slash=True,
                open_browser=True,
                authorization_prompt_message="Complete Sheets consent in your browser.",
                success_message="Sheets authorization complete. You may close this window.",
                access_type="offline",
                prompt="consent",
            )
            token = result.refresh_token
            if not isinstance(token, str) or not token.strip():
                raise AuthError("Google returned no refresh token; repeat Sheets consent.")
        except AuthError:
            raise
        except Exception:
            raise AuthError("Sheets authorization failed; check the OAuth client and retry.") from None

    token_path = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", prefix="weather-tracker-refresh-", dir="/tmp", delete=False
        ) as stream:
            token_path = Path(stream.name)
            os.fchmod(stream.fileno(), 0o600)
            stream.write(token)
        return token_path
    except Exception:
        if token_path is not None:
            token_path.unlink(missing_ok=True)
        raise AuthError("Could not save the Sheets refresh token securely.") from None
