"""
SpeedMon - API + scheduler + notifiche + serving frontend.

Avvio:  uvicorn main:app --host 0.0.0.0 --port 8765
"""
from __future__ import annotations

import os
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from fastapi import Body, FastAPI, HTTPException, Query
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

import db
import notify
from engines import SpeedtestError, build_engine

STATIC_DIR = Path(__file__).parent / "static"
DEFAULT_PORT = int(os.getenv("SPEEDMON_PORT", "8765"))

scheduler = BackgroundScheduler(timezone="UTC")


# ------------------------------------------------------------ core job
def run_measurement() -> dict:
    """Esegue una misura, la salva, valuta soglie e notifica. Non solleva mai."""
    settings = db.get_settings()
    engine_name = settings.get("engine", "ookla")
    server_id = settings.get("server_id")
    try:
        engine = build_engine(engine_name, server_id=server_id)
        result = engine.run()
        rid = db.insert_result(result, ok=True)
        # valutazione soglie -> notifica
        violations = notify.check_thresholds(result, settings)
        if violations:
            subject, email_body, tg_body, email_html = notify.build_threshold_msg(result, violations)
            notify.dispatch(settings, subject, email_body, tg_body, email_html)
        return {"id": rid, "ok": True, "violations": violations, **result}
    except SpeedtestError as e:
        db.insert_result({"engine": engine_name}, ok=False, error=str(e))
        # avvisa del fallimento
        subject, email_body, tg_body, email_html = notify.build_failure_msg(engine_name, str(e))
        notify.dispatch(settings, subject, email_body, tg_body, email_html)
        return {"ok": False, "error": str(e)}


def send_report() -> None:
    """Report periodico via email con riepilogo delle ultime misure."""
    settings = db.get_settings()
    rep = settings.get("report", {})
    if not rep.get("enabled") or not rep.get("to"):
        return
    hours = 168 if rep.get("frequency") == "weekly" else 720
    s = db.get_stats(hours)
    outages = db.get_outages(hours)
    period = "settimanale" if hours == 168 else "mensile"
    contract = settings.get("contract_download")
    pct = None
    if contract and s["download"]["avg"]:
        pct = round(s["download"]["avg"] / contract * 100)
    subject, body, html = notify.build_report_msg(s, len(outages), period, pct, contract)
    email_cfg = settings.get("notify", {}).get("email", {})
    cfg = {**email_cfg, "to": rep["to"]}
    try:
        notify.send_email(cfg, subject, body, html=html)
    except Exception:  # noqa: BLE001
        pass


def _reschedule() -> None:
    """(Ri)programma i job in base alle impostazioni correnti."""
    settings = db.get_settings()
    interval = int(settings.get("interval_min", 60))
    scheduler.add_job(run_measurement, "interval", minutes=interval,
                      id="speedtest", replace_existing=True,
                      max_instances=1, coalesce=True)
    # report
    rep = settings.get("report", {})
    scheduler.remove_all_jobs("report") if False else None
    try:
        scheduler.remove_job("report")
    except Exception:  # noqa: BLE001
        pass
    if rep.get("enabled"):
        hh, mm = (rep.get("time", "08:00").split(":") + ["0"])[:2]
        if rep.get("frequency") == "weekly":
            trig = CronTrigger(day_of_week="mon", hour=int(hh), minute=int(mm))
        else:
            trig = CronTrigger(day=1, hour=int(hh), minute=int(mm))
        scheduler.add_job(send_report, trig, id="report", replace_existing=True)


@asynccontextmanager
async def lifespan(app: FastAPI):
    db.init_db()
    _reschedule()
    scheduler.start()
    yield
    scheduler.shutdown(wait=False)


app = FastAPI(title="SpeedMon", version="1.0.0", lifespan=lifespan)


# ------------------------------------------------------------ API: dati
@app.get("/api/results")
def api_results(hours: int | None = Query(None, ge=1, le=8760),
                limit: int = Query(5000, ge=1, le=20000)):
    return db.get_results(hours=hours, limit=limit)


@app.get("/api/stats")
def api_stats(hours: int = Query(24, ge=1, le=8760)):
    return db.get_stats(hours=hours)


@app.get("/api/hourly")
def api_hourly(hours: int = Query(168, ge=24, le=8760)):
    return db.get_hourly_worst(hours=hours)


@app.get("/api/outages")
def api_outages(hours: int = Query(720, ge=1, le=8760)):
    return db.get_outages(hours=hours)


@app.post("/api/run")
def api_run_now():
    result = run_measurement()
    if not result.get("ok"):
        raise HTTPException(status_code=502, detail=result.get("error"))
    return result


@app.get("/api/export")
def api_export(hours: int | None = Query(None, ge=1, le=8760)):
    rows = db.get_results(hours=hours, limit=20000)
    return JSONResponse(content=rows,
                        headers={"Content-Disposition": "attachment; filename=speedmon_export.json"})


# ------------------------------------------------------------ API: settings
@app.get("/api/settings")
def api_get_settings():
    s = db.get_settings()
    # non esporre le password in chiaro verso il frontend
    s = _mask_secrets(s)
    return s


@app.put("/api/settings")
def api_put_settings(payload: dict = Body(...)):
    current = db.get_settings()
    merged = _merge_settings(current, payload)
    db.save_settings(merged)
    _reschedule()
    return _mask_secrets(db.get_settings())


@app.get("/api/servers")
def api_servers():
    """Elenca i server disponibili per il motore configurato."""
    settings = db.get_settings()
    try:
        engine = build_engine(settings.get("engine", "ookla"))
        return engine.servers()
    except SpeedtestError as e:
        raise HTTPException(status_code=502, detail=str(e))


@app.post("/api/test-notify")
def api_test_notify(channel: str = Query(..., pattern="^(email|telegram)$")):
    settings = db.get_settings()
    cfg = settings.get("notify", {})
    try:
        if channel == "email":
            notify.send_email(cfg.get("email", {}), "SpeedMon - prova",
                              "Notifica di prova da SpeedMon.")
        else:
            notify.send_telegram(cfg.get("telegram", {}), "SpeedMon - notifica di prova")
        return {"ok": True}
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=str(e))


# ------------------------------------------------------------ helper
_SECRET_KEYS = {"smtp_pass", "bot_token"}


def _mask_secrets(s: dict) -> dict:
    s = {**s}
    notify_cfg = {**s.get("notify", {})}
    if "email" in notify_cfg:
        email = {**notify_cfg["email"]}
        if email.get("smtp_pass"):
            email["smtp_pass"] = "********"
        notify_cfg["email"] = email
    if "telegram" in notify_cfg:
        tg = {**notify_cfg["telegram"]}
        if tg.get("bot_token"):
            tg["bot_token"] = "********"
        notify_cfg["telegram"] = tg
    s["notify"] = notify_cfg
    return s


def _merge_settings(current: dict, incoming: dict) -> dict:
    """Merge profondo. Ignora i secret mascherati (********) per non cancellarli."""
    out = {**current}
    for k, v in incoming.items():
        if isinstance(v, dict) and isinstance(current.get(k), dict):
            out[k] = _merge_settings(current[k], v)
        elif v == "********":
            continue  # mantieni il secret esistente
        else:
            out[k] = v
    return out


# ------------------------------------------------------------ frontend
if STATIC_DIR.exists():
    if (STATIC_DIR / "assets").exists():
        app.mount("/assets", StaticFiles(directory=STATIC_DIR / "assets"), name="assets")

    @app.get("/")
    def index():
        return FileResponse(STATIC_DIR / "index.html")

    @app.get("/{path:path}")
    def spa(path: str):
        f = STATIC_DIR / path
        if f.is_file():
            return FileResponse(f)
        return FileResponse(STATIC_DIR / "index.html")
