from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class CookieFile:
    # X web session cookies
    auth_token: str | None
    ct0: str | None
    guest_id: str | None
    # X GraphQL bearer token (not a cookie; typically from Authorization header)
    x_bearer: str | None

    # Periscope guest cookie used for authorizeToken/turnServers
    atu_cookie: str | None

    # Optional extra periscope inputs that callers may store in the same file.
    chat_token: str | None
    # Optional: pre-known ids for quick CLI use.
    broadcast_id: str | None
    query_id: str | None


def _parse_key_value_line(line: str) -> tuple[str, str] | None:
    # Supports: key=value
    if "=" not in line:
        return None
    key, value = line.split("=", 1)
    key = key.strip()
    value = value.strip()
    if not key:
        return None
    return key, value


def _parse_netscape_line(parts: list[str]) -> tuple[str, str] | None:
    # Netscape cookie format:
    # domain, flag, path, secure, expiration, name, value
    if len(parts) < 7:
        return None
    name = parts[5].strip()
    value = parts[6].strip()
    if not name:
        return None
    return name, value


def load_cookie_file(path: str | Path) -> CookieFile:
    p = Path(path).expanduser().resolve()
    text = p.read_text(encoding="utf-8", errors="replace")

    kv: dict[str, str] = {}

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith("#") or line.startswith("//"):
            continue

        # Netscape cookies are tab-separated.
        if "\t" in raw_line and "=" not in raw_line:
            parts = [x.strip() for x in raw_line.split("\t") if x.strip()]
            parsed = _parse_netscape_line(parts)
            if parsed is not None:
                k, v = parsed
                kv[k] = v
                continue

        parsed = _parse_key_value_line(line)
        if parsed is not None:
            k, v = parsed
            kv[k] = v

    # Accept a few aliases to make the file less brittle.
    auth_token = kv.get("auth_token")
    ct0 = kv.get("ct0")
    guest_id = kv.get("guest_id")
    x_bearer = kv.get("x_bearer") or kv.get("xBearer") or kv.get("bearer")

    atu_cookie = (
        kv.get("atu_cookie")
        or kv.get("atu")
        or kv.get("periscope_cookie")
        or kv.get("pscp_cookie")
    )

    chat_token = kv.get("chat_token")
    broadcast_id = kv.get("broadcast_id")
    query_id = kv.get("query_id")

    return CookieFile(
        auth_token=auth_token,
        ct0=ct0,
        guest_id=guest_id,
        x_bearer=x_bearer,
        atu_cookie=atu_cookie,
        chat_token=chat_token,
        broadcast_id=broadcast_id,
        query_id=query_id,
    )


def resolve_default_cookie_path() -> Path | None:
    # env override first
    import os

    env_path = os.environ.get("XSPACEKIT_COOKIE_FILE")
    if env_path:
        return Path(env_path).expanduser().resolve()

    # local working directory: cookie.txt
    local = Path("cookie.txt")
    if local.exists():
        return local.resolve()

    # common config dir
    xdg = Path.home() / ".config" / "xspacekit" / "cookie.txt"
    if xdg.exists():
        return xdg

    return None


def require_cookie_value(value: str | None, field: str) -> str:
    if value is None or value == "":
        raise ValueError(f"Missing required cookie field: {field}")
    return value


def require_cookie_file_fields(cfg: CookieFile) -> None:
    # Only enforce the X web session pieces that are required for GraphQL.
    require_cookie_value(cfg.auth_token, "auth_token")
    require_cookie_value(cfg.ct0, "ct0")
    require_cookie_value(cfg.guest_id, "guest_id")
    require_cookie_value(cfg.x_bearer, "x_bearer")

    # For Periscope guest auth.
    # `atu_cookie` can be derived dynamically via AuthenticatePeriscope + loginTwitterToken,
    # so we treat it as optional at the cookie file level (CLI can choose legacy or auto modes).
