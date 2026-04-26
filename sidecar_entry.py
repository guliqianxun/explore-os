"""ft-023: Python sidecar entry point for Electron shell + PyInstaller bundle.

Behavior
--------
1. Parse ``--port`` (0 = OS picks free port) / ``--data-dir`` / ``--host``.
2. Set ``EXPLORE_OS_DATA_DIR`` **before** Django setup so that
   ``apps.core.paths`` import side-effects (HF_HOME / TRANSFORMERS_CACHE
   redirect) land on the right tree.
3. ``django.setup()`` then run ``migrate --noinput`` (idempotent first-run).
4. Start Waitress on ``host:port``; print
   ``[sidecar] listening on http://<host>:<port>``  to stdout (parsed by
   the Electron main process to discover the actual port when port=0).

This module is the PyInstaller entry as well as the dev-mode entry
(``uv run python sidecar_entry.py --data-dir <dir> --port 0``).
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(
        description="explore-os Django sidecar (Waitress)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=0,
        help="Port to bind. 0 (default) lets the OS pick a free port; "
             "actual chosen port is printed to stdout.",
    )
    parser.add_argument(
        "--data-dir",
        required=True,
        help="EXPLORE_OS_DATA_DIR — root for sqlite, media, cache, outbox, etc.",
    )
    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="Host interface to bind (default 127.0.0.1, localhost only).",
    )
    parser.add_argument(
        "--threads",
        type=int,
        default=8,
        help="Waitress worker threads (default 8).",
    )
    parser.add_argument(
        "--skip-migrate",
        action="store_true",
        help="Skip running migrate on startup (e.g. when caller pre-migrated).",
    )
    args = parser.parse_args()

    # Must be set before Django imports apps.core.paths (HF_HOME side effect).
    os.environ["EXPLORE_OS_DATA_DIR"] = args.data_dir
    # ft-024 follow-up: explicitly override DATABASE_URL so any value baked into
    # the dev .env (which may point at the in-repo sqlite) cannot leak into the
    # desktop sidecar. Desktop must always store data under DATA_DIR.
    os.environ["DATABASE_URL"] = (
        f"sqlite:///{Path(args.data_dir) / 'explore_os.sqlite3'}"
    )
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    # PyInstaller-frozen exe should always run unbuffered so the
    # "listening on" line surfaces to the parent immediately.
    os.environ.setdefault("PYTHONUNBUFFERED", "1")

    import django

    django.setup()

    if not args.skip_migrate:
        from django.core.management import call_command

        call_command("migrate", "--noinput")

    from waitress import create_server

    from config.wsgi import application

    server = create_server(
        application,
        host=args.host,
        port=args.port,
        threads=args.threads,
    )
    # When port=0, OS allocated something — surface the real port.
    # ``waitress.create_server`` returns a ``TcpWSGIServer`` whose listening
    # socket is exposed as ``.socket`` (single-adapter case). When binding
    # multiple adapters (host=*), waitress instead returns a ``MultiSocketServer``
    # exposing ``.effective_listen`` / ``.adj``. Cover both for safety.
    actual_port: int
    sock = getattr(server, "socket", None)
    if sock is not None:
        actual_port = sock.getsockname()[1]
    else:
        # MultiSocketServer path: use the first underlying server.
        effective = getattr(server, "effective_listen", None)
        if effective:
            actual_port = int(effective[0][1])
        else:
            actual_port = int(getattr(server, "adj").port)
    print(
        f"[sidecar] listening on http://{args.host}:{actual_port}",
        flush=True,
    )
    sys.stdout.flush()
    server.run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
