"""
Notifiche (email SMTP + Telegram) e valutazione soglie.

- check_thresholds(): confronta una misura con la soglia della fascia oraria
  attiva (o con le soglie globali di fallback) e ritorna la lista di violazioni.
- dispatch(): invia il messaggio sui canali abilitati.
"""
from __future__ import annotations

import smtplib
import ssl
import urllib.parse
import urllib.request
from datetime import datetime
from email.message import EmailMessage


# ------------------------------------------------------------ soglie
def _in_band(now_hhmm: str, start: str, end: str) -> bool:
    """True se now e' dentro [start, end). Gestisce fasce che scavalcano mezzanotte."""
    if start <= end:
        return start <= now_hhmm < end
    # es. 23:00 -> 00:00 (scavalca)
    return now_hhmm >= start or now_hhmm < end


def active_download_threshold(settings: dict, when: datetime | None = None) -> tuple[float, str]:
    """Ritorna (soglia_download, nome_fascia) per l'ora corrente.

    Se nessuna fascia copre l'ora, usa la soglia globale.
    """
    when = when or datetime.now()
    hhmm = when.strftime("%H:%M")
    for band in settings.get("hourly_bands", []):
        if _in_band(hhmm, band["from"], band["to"]):
            return float(band["download_min"]), band["name"]
    return float(settings.get("thresholds", {}).get("download", 0)), "globale"


def check_thresholds(result: dict, settings: dict) -> list[str]:
    """Ritorna le violazioni testuali (vuoto se tutto ok)."""
    violations = []
    thr = settings.get("thresholds", {})
    dl_min, band_name = active_download_threshold(settings)

    if result.get("download_mbps") is not None and result["download_mbps"] < dl_min:
        violations.append(
            f"Download {result['download_mbps']} Mbps sotto la soglia "
            f"{dl_min:.0f} (fascia {band_name})"
        )
    ul_min = thr.get("upload")
    if ul_min and result.get("upload_mbps") is not None and result["upload_mbps"] < ul_min:
        violations.append(f"Upload {result['upload_mbps']} Mbps sotto la soglia {ul_min}")
    pg_max = thr.get("ping")
    if pg_max and result.get("ping_ms") is not None and result["ping_ms"] > pg_max:
        violations.append(f"Ping {result['ping_ms']} ms sopra la soglia {pg_max}")
    return violations


# ------------------------------------------------------------ invio
def send_email(cfg: dict, subject: str, body: str) -> None:
    if not cfg.get("to") or not cfg.get("smtp_host"):
        raise ValueError("Configurazione email incompleta")
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = cfg.get("smtp_user") or cfg["to"]
    msg["To"] = cfg["to"]
    msg.set_content(body)

    port = int(cfg.get("smtp_port", 587))
    ctx = ssl.create_default_context()
    if port == 465:
        with smtplib.SMTP_SSL(cfg["smtp_host"], port, context=ctx, timeout=20) as s:
            _login_send(s, cfg, msg)
    else:
        with smtplib.SMTP(cfg["smtp_host"], port, timeout=20) as s:
            s.starttls(context=ctx)
            _login_send(s, cfg, msg)


def _login_send(server, cfg, msg):
    if cfg.get("smtp_user") and cfg.get("smtp_pass"):
        server.login(cfg["smtp_user"], cfg["smtp_pass"])
    server.send_message(msg)


def send_telegram(cfg: dict, text: str) -> None:
    if not cfg.get("bot_token") or not cfg.get("chat_id"):
        raise ValueError("Configurazione Telegram incompleta")
    url = f"https://api.telegram.org/bot{cfg['bot_token']}/sendMessage"
    data = urllib.parse.urlencode(
        {"chat_id": cfg["chat_id"], "text": text, "parse_mode": "HTML"}
    ).encode()
    req = urllib.request.Request(url, data=data)
    with urllib.request.urlopen(req, timeout=20) as resp:
        if resp.status != 200:
            raise RuntimeError(f"Telegram HTTP {resp.status}")


def dispatch(settings: dict, subject: str, body: str) -> dict:
    """Invia sui canali abilitati. Ritorna esito per canale (non solleva)."""
    notify = settings.get("notify", {})
    out = {}
    email_cfg = notify.get("email", {})
    if email_cfg.get("enabled"):
        try:
            send_email(email_cfg, subject, body)
            out["email"] = "ok"
        except Exception as e:  # noqa: BLE001
            out["email"] = f"errore: {e}"
    tg_cfg = notify.get("telegram", {})
    if tg_cfg.get("enabled"):
        try:
            send_telegram(tg_cfg, f"<b>{subject}</b>\n{body}")
            out["telegram"] = "ok"
        except Exception as e:  # noqa: BLE001
            out["telegram"] = f"errore: {e}"
    return out
