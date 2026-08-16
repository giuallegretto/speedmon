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
def send_email(cfg: dict, subject: str, body: str, html: str | None = None) -> None:
    if not cfg.get("to") or not cfg.get("smtp_host"):
        raise ValueError("Configurazione email incompleta")
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = cfg.get("smtp_user") or cfg["to"]
    msg["To"] = cfg["to"]
    msg.set_content(body)  # fallback testo semplice
    if html:
        msg.add_alternative(html, subtype="html")  # versione ricca

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


def dispatch(settings: dict, subject: str, email_body: str,
             telegram_body: str | None = None, email_html: str | None = None) -> dict:
    """Invia sui canali abilitati. Ritorna esito per canale (non solleva).

    email_body    -> testo semplice per l'email (fallback)
    email_html    -> versione HTML dell'email (se None, solo testo)
    telegram_body -> HTML per Telegram; se None, riusa email_body con subject in grassetto
    """
    notify = settings.get("notify", {})
    out = {}
    email_cfg = notify.get("email", {})
    if email_cfg.get("enabled"):
        try:
            send_email(email_cfg, subject, email_body, html=email_html)
            out["email"] = "ok"
        except Exception as e:  # noqa: BLE001
            out["email"] = f"errore: {e}"
    tg_cfg = notify.get("telegram", {})
    if tg_cfg.get("enabled"):
        tg = telegram_body if telegram_body is not None else f"<b>{subject}</b>\n{email_body}"
        try:
            send_telegram(tg_cfg, tg)
            out["telegram"] = "ok"
        except Exception as e:  # noqa: BLE001
            out["telegram"] = f"errore: {e}"
    return out


# ------------------------------------------------------------ template messaggi
def _fmt_when(dt: datetime | None = None) -> str:
    dt = dt or datetime.now()
    return dt.strftime("%d/%m alle %H:%M")


def build_threshold_msg(result: dict, violations: list[str]) -> tuple[str, str, str, str]:
    """(subject, email_body, telegram_html, email_html) per l'avviso di soglia."""
    import email_templates as et
    subject = "SpeedMon — Soglia superata"
    when = _fmt_when()
    server = result.get("server", "?")

    lines = "\n".join(f"  • {v}" for v in violations)
    email_body = (
        "La connessione e' scesa sotto i valori attesi.\n\n"
        f"{lines}\n\n"
        f"Server: {server}\n"
        f"Orario: {when}\n\n"
        "Controlla la dashboard per i dettagli."
    )
    tg_lines = "\n".join(f"📉 {v}" for v in violations)
    telegram = (
        "⚠️ <b>SpeedMon — Soglia superata</b>\n\n"
        "La connessione è scesa sotto i valori attesi.\n\n"
        f"{tg_lines}\n"
        f"📡 <b>Server:</b> {server}\n"
        f"🕐 <b>Orario:</b> {when}\n\n"
        "<i>Controlla la dashboard per i dettagli.</i>"
    )
    email_html = et.threshold_html(result, violations, when)
    return subject, email_body, telegram, email_html


def build_failure_msg(engine: str, error: str) -> tuple[str, str, str, str]:
    """(subject, email_body, telegram_html, email_html) per il test fallito."""
    import email_templates as et
    subject = "SpeedMon — Test fallito"
    when = _fmt_when()
    email_body = (
        f"Il test di velocita' non e' riuscito: {error}\n\n"
        f"Motore: {engine}\n"
        f"Orario: {when}\n\n"
        "Se si ripete, potrebbe essere un'interruzione della linea."
    )
    telegram = (
        "🔴 <b>SpeedMon — Test fallito</b>\n\n"
        f"Il test di velocità non è riuscito: {error}\n\n"
        f"⚙️ <b>Motore:</b> {engine}\n"
        f"🕐 <b>Orario:</b> {when}\n\n"
        "<i>Se si ripete, potrebbe essere un'interruzione della linea.</i>"
    )
    email_html = et.failure_html(engine, error, when)
    return subject, email_body, telegram, email_html


def build_report_msg(stats: dict, outages: int, period_label: str,
                     contract_pct: int | None, contract_mbps: int | None) -> tuple[str, str, str]:
    """(subject, email_body, email_html) per il report periodico (solo email)."""
    import email_templates as et
    subject = f"SpeedMon — Report {period_label}"
    dl, ul, pg = stats["download"], stats["upload"], stats["ping"]
    sep = "━" * 20
    lines = [
        f"SpeedMon — Report {period_label}",
        f"Periodo: {'ultimi 7 giorni' if 'settiman' in period_label else 'ultimo mese'}",
        "",
        sep,
        f"⬇  Download   media {dl['avg']} Mbps  ·  min {dl['min']}  ·  max {dl['max']}",
        f"⬆  Upload     media {ul['avg']} Mbps  ·  min {ul['min']}  ·  max {ul['max']}",
        f"📶 Ping       media {pg['avg']} ms  ·  min {pg['min']}  ·  max {pg['max']}",
        sep,
        "",
        f"✅ Uptime: {stats['uptime_pct']}%  ({stats['failed_tests']} test falliti su {stats['total_tests']})",
    ]
    if contract_pct is not None and contract_mbps:
        lines.append(f"📄 Rispetto contratto: {contract_pct}% dei {contract_mbps} Mbps promessi")
    lines.append(f"⚠  Interruzioni rilevate: {outages}")
    lines += ["", "Report generato automaticamente da SpeedMon."]
    email_html = et.report_html(stats, outages, period_label, contract_pct, contract_mbps)
    return subject, "\n".join(lines), email_html
