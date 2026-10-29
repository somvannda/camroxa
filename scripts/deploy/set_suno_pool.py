#!/usr/bin/env python3
"""Set a Suno-compatible pool's keys and active upstream host on sandbox/production.

Adds keys tagged with a host (idempotently, by label) and points the provider's
active ``base_url`` at that host — the CLI equivalent of the admin Key Pool
provider setting. Both Suno-compatible providers now target Camxora's own
musicapi; they exist as separate provider ids only because AI Routing prices
them differently:

  * ``suno``               -> https://musicapi.camxora.com
  * ``camxora_music_api``  -> https://musicapi.camxora.com

Set the matching **Settings -> AI Routing -> Music Generation** provider too;
the routed provider is what drives the credit price and the generating host.

Examples:
    # Suno pool -> our musicapi, with two tagged keys
    python scripts/deploy/set_suno_pool.py --env sandbox --provider suno \
        --key "musicapi account 1=sk_..." --key "musicapi account 2=sk_..." \
        --base-url https://musicapi.camxora.com

    # Camxora Music API pool -> musicapi, with two tagged keys
    python scripts/deploy/set_suno_pool.py --env sandbox --provider camxora_music_api \
        --key "camxora desktop app=sk_..." --key "musicweb camxora=sk_..." \
        --base-url https://musicapi.camxora.com

    # roll back a provider to the environment default
    python scripts/deploy/set_suno_pool.py --env sandbox --provider camxora_music_api --clear

Keys are passed per invocation and never written to disk on the server beyond
the encrypted ``api_key_entries`` row.
"""

from __future__ import annotations

import argparse
import base64
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / ".venv" / "Lib" / "site-packages"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from deploy import (  # noqa: E402
    ensure_deploy_key,
    load_production_secrets,
    load_sandbox_secrets,
    resolve_production_ssh,
    resolve_sandbox_ssh,
    ssh_connect,
)

REMOTE = r'''
import asyncio
import base64
import json
import os

import asyncpg

from platform_api.config import get_settings
from platform_api.repositories.key_pool_repo import KeyPoolRepository
from platform_api.services.key_encryption import KeyEncryption
from platform_api.services.key_pool_service import KeyPoolService
from platform_api.services.suno_audio_resolver import poll_suno_generate_with_pool


async def main() -> None:
    settings = get_settings()
    # Helpers read a few values straight from os.environ (systemd provides them in
    # the real service); pydantic already parsed .env, so mirror them here.
    os.environ.setdefault("PLATFORM_ENCRYPTION_MASTER_KEY", settings.encryption_master_key or "")
    os.environ.setdefault("PLATFORM_SUNO_API_BASE_URL", settings.suno_api_base_url or "")
    os.environ.setdefault("PLATFORM_SUNO_CALLBACK_BASE_URL", settings.suno_callback_base_url or "")
    os.environ.setdefault("PLATFORM_SUNO_TIMEOUT_SECONDS", str(settings.suno_timeout_seconds))
    payload = json.loads(base64.b64decode(os.environ["CAMXORA_POOL_PAYLOAD"]).decode())
    provider = payload.get("provider", "suno")
    base_url = payload.get("base_url")
    clear = bool(payload.get("clear_base_url"))
    keys = payload.get("keys", [])

    dsn = settings.database_url.replace("postgresql+asyncpg://", "postgresql://", 1)
    pool = await asyncpg.create_pool(dsn)
    service = KeyPoolService(
        repository=KeyPoolRepository(pool=pool),
        encryption=KeyEncryption(settings.encryption_master_key),
        redis=None,
    )

    # Idempotent: drop any existing key with the same label before re-adding.
    labels = {k["label"] for k in keys}
    for entry in await service.list_keys(provider):
        if entry.label in labels:
            await service.remove_key(entry.id)
            print("removed existing", entry.label)

    for item in keys:
        key_id = await service.add_key(
            provider,
            item["key"],
            item["label"],
            int(item.get("priority", 50)),
            base_url=base_url,
        )
        print("added", item["label"], key_id)

    tag_host = payload.get("tag_existing_untagged")
    if tag_host:
        tagged = await pool.fetch(
            "UPDATE api_key_entries SET base_url = $1 "
            "WHERE provider = $2 AND base_url IS NULL RETURNING id",
            tag_host,
            provider,
        )
        print("tagged_existing_untagged", len(tagged), tag_host)

    if clear:
        await service.configure_provider(provider, clear_base_url=True)
    elif base_url is not None:
        await service.configure_provider(provider, base_url=base_url)

    config = await service.get_provider_config(provider)
    print("provider_config", provider, "base_url=", config.base_url)
    for entry in await service.list_keys(provider):
        print("key", entry.label, entry.status.value, "base_url=", entry.base_url)

    verify_task_id = payload.get("verify_task_id")
    if verify_task_id:
        result = await poll_suno_generate_with_pool(
            pool, verify_task_id, provider=provider
        )
        print(
            "verify_poll state=",
            result.state,
            "error=",
            result.error,
            "audio_url_ok=",
            (result.audio_url_ok or "")[:90],
        )

    await pool.close()


asyncio.run(main())
'''


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env", choices=["sandbox", "production"], required=True)
    parser.add_argument(
        "--provider",
        choices=["suno", "camxora_music_api"],
        default="suno",
        help="Suno-compatible provider pool to configure (default: suno).",
    )
    parser.add_argument(
        "--key",
        action="append",
        default=[],
        help="label=key_value (repeatable)",
    )
    parser.add_argument("--base-url", default=None)
    parser.add_argument("--clear", action="store_true")
    parser.add_argument(
        "--tag-existing",
        default=None,
        help="Set base_url on existing untagged provider keys (e.g. the legacy host), "
        "so a later rollback can select them.",
    )
    parser.add_argument(
        "--verify-task-id",
        default=None,
        help="Poll this musicapi task through the pool after applying (integration check).",
    )
    args = parser.parse_args()

    keys: list[dict[str, object]] = []
    for item in args.key:
        label, _, value = item.partition("=")
        if not label or not value:
            print(f"bad --key (expected label=value): {item[:24]}...")
            return 2
        keys.append({"label": label, "key": value})

    if (
        not keys
        and not args.clear
        and args.base_url is None
        and not args.verify_task_id
        and not args.tag_existing
    ):
        print("Nothing to do: pass --key, --base-url, --clear, --tag-existing, or --verify-task-id.")
        return 2

    payload = base64.b64encode(
        json.dumps(
            {
                "provider": args.provider,
                "base_url": args.base_url,
                "clear_base_url": args.clear,
                "keys": keys,
                "tag_existing_untagged": args.tag_existing,
                "verify_task_id": args.verify_task_id,
            }
        ).encode()
    ).decode()

    if args.env == "sandbox":
        secrets = load_sandbox_secrets()
        host, user, password = resolve_sandbox_ssh(secrets)
    else:
        secrets = load_production_secrets()
        host, user, password = resolve_production_ssh(secrets)
    print(f"Target {args.env} host: {host}")

    client = ssh_connect(host, user, ensure_deploy_key(), password)
    sftp = client.open_sftp()
    with sftp.file("/tmp/set_suno_pool.py", "w") as remote_file:
        remote_file.write(REMOTE)
    sftp.close()

    # Do not `source .env` in the shell: it strips the quotes around JSON values
    # like PLATFORM_CORS_ORIGINS and breaks pydantic parsing. Settings reads
    # platform_api/.env itself (relative to the repo cwd).
    cmd = (
        "sudo -u camxora bash -lc 'cd /opt/camxora/repo && "
        f"CAMXORA_POOL_PAYLOAD={payload} PYTHONPATH=/opt/camxora/repo "
        "platform_api/.venv/bin/python /tmp/set_suno_pool.py'"
    )
    _, stdout, stderr = client.exec_command(cmd, get_pty=True)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    sys.stdout.buffer.write(out.encode("utf-8", errors="replace"))
    if err.strip():
        sys.stdout.buffer.write(("STDERR: " + err).encode("utf-8", errors="replace"))
    code = stdout.channel.recv_exit_status()
    client.close()
    return code


if __name__ == "__main__":
    raise SystemExit(main())
