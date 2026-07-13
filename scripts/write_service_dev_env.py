#!/usr/bin/env python3
"""Write the ignored Docker-to-local-Supabase endpoint contract for service-dev."""

from __future__ import annotations

import json
import os
import secrets
import subprocess
from pathlib import Path
from urllib.parse import quote, urlsplit, urlunsplit


ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / ".env.service-dev"
NPX = os.environ.get("APE_NPX_BIN") or ("npx.cmd" if os.name == "nt" else "npx")


def _netloc_with_host(url: str, host: str) -> str:
    parsed = urlsplit(url)
    auth = ""
    if parsed.username is not None:
        auth = quote(parsed.username, safe="")
        if parsed.password is not None:
            auth += f":{quote(parsed.password, safe='')}"
        auth += "@"
    port = f":{parsed.port}" if parsed.port is not None else ""
    return f"{auth}{host}{port}"


def docker_host_url(url: str) -> str:
    """Make a CLI endpoint reachable from an APE container on Linux or WSL."""

    parsed = urlsplit(url)
    if parsed.hostname not in {"127.0.0.1", "localhost"}:
        return url
    return urlunsplit(
        (
            parsed.scheme,
            _netloc_with_host(url, "host.docker.internal"),
            parsed.path,
            parsed.query,
            parsed.fragment,
        )
    )


def sqlalchemy_url(database_url: str, driver: str) -> str:
    parsed = urlsplit(docker_host_url(database_url))
    if parsed.scheme != "postgresql":
        raise ValueError("Supabase DB_URL must use the postgresql scheme")
    return urlunsplit(
        (
            f"postgresql+{driver}",
            parsed.netloc,
            parsed.path,
            parsed.query,
            parsed.fragment,
        )
    )


def previous_secret() -> str | None:
    if not TARGET.exists():
        return None
    for line in TARGET.read_text(encoding="utf-8").splitlines():
        key, separator, value = line.partition("=")
        if separator and key == "APE_AUTH_JWT_SECRET" and value:
            return value
    return None


def local_supabase_status() -> dict[str, str]:
    completed = subprocess.run(
        [NPX, "--yes", "supabase", "status", "--output", "json"],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode:
        raise RuntimeError("Supabase is not running; start it before generating service-dev env")
    try:
        status = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError("Supabase CLI did not return status JSON") from exc
    required = {"API_URL", "DB_URL"}
    if missing := required.difference(status):
        raise RuntimeError(f"Supabase status is missing: {', '.join(sorted(missing))}")
    return status


def main() -> None:
    status = local_supabase_status()
    secret = previous_secret() or secrets.token_urlsafe(48)
    content = "\n".join(
        (
            "# Generated from `supabase status`; never commit this file.",
            "# APE_AUTH_JWT_SECRET is temporary legacy-service compatibility only.",
            f"APE_DATABASE_SYNC_URL={sqlalchemy_url(status['DB_URL'], 'psycopg')}",
            f"APE_DATABASE_ASYNC_URL={sqlalchemy_url(status['DB_URL'], 'asyncpg')}",
            f"APE_SUPABASE_URL={docker_host_url(status['API_URL'])}",
            f"APE_AUTH_JWT_SECRET={secret}",
            "",
        )
    )
    TARGET.write_text(content, encoding="utf-8")
    try:
        TARGET.chmod(0o600)
    except OSError:
        pass
    print("Wrote .env.service-dev with local Docker endpoints.")


if __name__ == "__main__":
    main()
