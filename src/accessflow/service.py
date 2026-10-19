"""Local operations API and one supervised in-process worker thread."""

import asyncio
import hmac
import logging
import threading
import time
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException
from fastapi.responses import JSONResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from accessflow.config import SafetyError, Settings
from accessflow.worker import Worker, retry_job
from accessflow.worker_store import WorkerStore


def create_app(settings=None, *, worker_factory=Worker):
    settings = settings or Settings()
    if len(settings.accessflow_admin_token.get_secret_value()) < 32:
        raise SafetyError(
            "Set ACCESSFLOW_ADMIN_TOKEN to a private random value of at least 32 characters"
        )
    settings.require_target()
    _ = settings.request_types
    worker = worker_factory(settings)

    @asynccontextmanager
    async def lifespan(app):
        def run_worker():
            try:
                worker.run()
            except Exception:
                logging.getLogger("accessflow.worker").error(
                    "Worker exited unexpectedly; inspect local state and configuration"
                )
            finally:
                if not worker.stop.is_set():
                    app.state.shutdown()

        thread = threading.Thread(target=run_worker, name="accessflow-worker", daemon=True)
        app.state.worker_thread = thread
        thread.start()
        try:
            yield
        finally:
            worker.stop.set()
            # Finish the in-flight bounded HTTP operation before closing the process.
            await asyncio.to_thread(thread.join, 30)

    app = FastAPI(
        title="AccessFlow operations",
        lifespan=lifespan,
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )
    app.state.worker = worker
    app.state.shutdown = lambda: worker.stop.set()
    bearer = HTTPBearer(auto_error=False)

    def authenticated(
        credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
    ):
        if (
            not credentials
            or credentials.scheme.lower() != "bearer"
            or not hmac.compare_digest(
                credentials.credentials.encode(),
                settings.accessflow_admin_token.get_secret_value().encode(),
            )
        ):
            raise HTTPException(
                401, "Authentication required", headers={"WWW-Authenticate": "Bearer"}
            )

    def status():
        with WorkerStore(settings.database_path()) as store:
            return store.overview(settings.jira_site_url)

    @app.get("/health")
    def health():
        runtime = status()["runtime"]
        thread = getattr(app.state, "worker_thread", None)
        current_run_polled = False
        try:
            started = datetime.fromisoformat(runtime["started_at"])
            succeeded = datetime.fromisoformat(runtime["last_successful_poll"])
            current_run_polled = bool(started.tzinfo and succeeded.tzinfo and succeeded >= started)
        except (KeyError, TypeError, ValueError):
            pass
        healthy = bool(
            thread
            and thread.is_alive()
            and runtime.get("run_id") == worker.run_id
            and runtime.get("state") in ("polling", "waiting")
            and current_run_polled
            and time.time() - runtime.get("heartbeat", 0) <= 30
            and time.time() <= runtime.get("next_poll_at", time.time()) + 60
        )
        return JSONResponse(
            {
                "healthy": healthy,
                "mode": "write"
                if settings.accessflow_worker_write_enabled and not settings.accessflow_dry_run
                else "dry_run",
            },
            status_code=200 if healthy else 503,
        )

    @app.get("/admin/status", dependencies=[Depends(authenticated)])
    def admin_status():
        return status()

    @app.get("/admin/issues/{key}", dependencies=[Depends(authenticated)])
    def show(key: str):
        try:
            settings.assert_issue_key(key)
            with WorkerStore(settings.database_path()) as store:
                return store.latest(settings.jira_site_url, key)
        except SafetyError:
            raise HTTPException(404, "No configured issue result") from None

    @app.get("/admin/issues/{key}/audit", dependencies=[Depends(authenticated)])
    def audit(key: str, limit: int = 100):
        try:
            settings.assert_issue_key(key)
            if not 1 <= limit <= 1000:
                raise SafetyError("Invalid limit")
            with WorkerStore(settings.database_path()) as store:
                return store.history(settings.jira_site_url, key, limit)
        except SafetyError:
            raise HTTPException(400, "Invalid configured issue or limit") from None

    @app.post("/admin/issues/{key}/retry", dependencies=[Depends(authenticated)])
    def retry(key: str):
        try:
            return retry_job(settings, key)
        except SafetyError as exc:
            raise HTTPException(409, str(exc)) from None

    @app.post("/admin/shutdown", dependencies=[Depends(authenticated)])
    def shutdown():
        worker.stop.set()
        app.state.shutdown()
        return {"stopping": True}

    return app


def serve(settings):
    import uvicorn

    logging.basicConfig(level=settings.log_level, format="%(asctime)s %(levelname)s %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)
    app = create_app(settings)
    server = uvicorn.Server(
        uvicorn.Config(
            app,
            host=settings.accessflow_bind_host,
            port=settings.accessflow_port,
            access_log=False,
            timeout_graceful_shutdown=45,
        )
    )

    def shutdown():
        server.should_exit = True

    app.state.shutdown = shutdown
    server.run()
