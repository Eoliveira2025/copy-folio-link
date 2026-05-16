"""Optional FastAPI server with health/status endpoints."""
from __future__ import annotations

import threading

import uvicorn
from fastapi import FastAPI

from app.config import settings
from app.mt5 import account_session, terminal_manager
from app.redis_client import get_redis, ping
from app.workers import audit_worker, execution_worker


def build_app() -> FastAPI:
    app = FastAPI(title="CopyTrade Pro Bridge Executor", version="0.1.0")

    @app.get("/health")
    def health():
        return {
            "status": "ok",
            "executor_id": settings.executor_id,
            "redis": "connected" if ping() else "disconnected",
            "mt5": "available" if terminal_manager.is_available() else "unavailable",
            "mode": settings.executor_mode,
            "real_trading": settings.enable_real_trading,
        }

    @app.get("/status")
    def status():
        return {
            "execution": execution_worker.metrics,
            "audit": audit_worker.audit_metrics,
        }

    @app.get("/accounts")
    def accounts():
        s = account_session.current_session()
        return {"current": None if s is None else {"login": s.login, "server": s.server}}

    @app.get("/queues")
    def queues():
        r = get_redis()
        out = []
        for prefix in (settings.queue_prefix, settings.audit_check_prefix, settings.audit_fix_prefix):
            for k in r.scan_iter(match=f"{prefix}:*", _type="list", count=200):
                out.append({"queue": k, "len": r.llen(k)})
        return {"queues": out}

    return app


def serve_in_thread(stop_event: threading.Event) -> threading.Thread:
    app = build_app()
    config = uvicorn.Config(
        app, host=settings.health_api_host, port=settings.health_api_port,
        log_level=settings.log_level.lower(), access_log=False,
    )
    server = uvicorn.Server(config)

    def _run():
        server.run()

    t = threading.Thread(target=_run, name="health-api", daemon=True)
    t.start()

    def _watch():
        stop_event.wait()
        server.should_exit = True

    threading.Thread(target=_watch, daemon=True).start()
    return t
