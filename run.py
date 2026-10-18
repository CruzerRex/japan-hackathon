"""Kizuna Forge launcher.

    python run.py                 start the server (creates/migrates the DB; seeds the demo on first run)
    python run.py --reset         wipe the database and re-seed the simulated demo organisation
    python run.py --seed-only     re-seed and exit
    python run.py --port 8080     choose a port
"""
from __future__ import annotations

import argparse
import logging
import sys

from kizuna.api import create_app
from kizuna.config import load_settings
from kizuna.logging_setup import log, setup_logging
from kizuna.web import make_server


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Kizuna Forge server")
    parser.add_argument("--reset", action="store_true", help="wipe and re-seed the demo database")
    parser.add_argument("--seed-only", action="store_true", help="re-seed the demo database and exit")
    parser.add_argument("--host")
    parser.add_argument("--port", type=int)
    args = parser.parse_args(argv)

    settings = load_settings()
    if args.host:
        settings.host = args.host
    if args.port:
        settings.port = args.port
    setup_logging(settings.log_level, settings.log_json)
    logger = logging.getLogger("kizuna")

    if args.reset or args.seed_only or not settings.db_path.exists():
        from kizuna.seed.seeder import DEMO_PASSWORD, seed
        log(logger, logging.INFO, "seeding_demo", db=str(settings.db_path))
        seed(settings.db_path, settings.upload_dir, settings=settings)
        log(logger, logging.INFO, "demo_ready", password_hint="see README (demo accounts)", accounts=9)
        if args.seed_only:
            print(f"Demo database ready at {settings.db_path}. Demo password: {DEMO_PASSWORD}")
            return 0

    app = create_app(settings)
    server = make_server(app, settings.host, settings.port)
    url = f"http://{settings.host}:{settings.port}"
    log(logger, logging.INFO, "server_started", url=url, demo_mode=settings.demo_mode,
        claude=app.settings.anthropic_enabled)
    print(f"\n  Kizuna Forge is running at {url}\n  Press Ctrl+C to stop.\n", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
