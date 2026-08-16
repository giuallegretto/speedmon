"""
Template email in HTML per SpeedMon.

Regole "email-safe": niente CSS esterno, stili inline, layout a tabelle,
colori espliciti. Testato per rendere bene su Gmail/Outlook/Apple Mail.

Ogni funzione ritorna una stringa HTML completa.
Il testo semplice resta come fallback in notify.py.
"""
from __future__ import annotations

# palette (coerente con l'app)
BG = "#0a0e17"
PANEL = "#111827"
EDGE = "#1e2a3d"
SIGNAL = "#3ddc84"
UPLOAD = "#4aa8ff"
AMBER = "#ffb03a"
BAD = "#ff5a5a"
TEXT = "#e6edf5"
DIM = "#6b7a90"
MONO = "'Courier New',Courier,monospace"
SANS = "Arial,Helvetica,sans-serif"


def _shell(inner: str, accent: str = SIGNAL) -> str:
    """Cornice comune: sfondo scuro, header con barra accento, footer."""
    return f"""\
<!doctype html>
<html>
<body style="margin:0;padding:0;background:{BG};">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:{BG};padding:28px 12px;">
<tr><td align="center">
  <table role="presentation" width="560" cellpadding="0" cellspacing="0" style="width:560px;max-width:100%;background:{PANEL};border:1px solid {EDGE};border-radius:14px;overflow:hidden;">
    <!-- barra accento -->
    <tr><td style="height:4px;background:{accent};font-size:0;line-height:0;">&nbsp;</td></tr>
    <!-- header -->
    <tr><td style="padding:24px 28px 8px;">
      <table role="presentation" cellpadding="0" cellspacing="0"><tr>
        <td style="font-family:{MONO};font-size:20px;font-weight:bold;color:{TEXT};letter-spacing:1px;">
          <span style="color:{accent};">&#9679;</span>&nbsp;SpeedMon
        </td>
      </tr></table>
    </td></tr>
    {inner}
    <!-- footer -->
    <tr><td style="padding:20px 28px 26px;border-top:1px solid {EDGE};">
      <p style="margin:0;font-family:{MONO};font-size:11px;color:{DIM};line-height:1.6;">
        Notifica automatica di SpeedMon &middot; monitor self-hosted della connessione
      </p>
    </td></tr>
  </table>
</td></tr>
</table>
</body>
</html>"""


def _row(label: str, value: str, color: str = TEXT) -> str:
    return f"""\
<tr>
  <td style="padding:8px 0;font-family:{MONO};font-size:12px;color:{DIM};text-transform:uppercase;letter-spacing:1px;width:120px;">{label}</td>
  <td style="padding:8px 0;font-family:{MONO};font-size:15px;color:{color};font-weight:bold;">{value}</td>
</tr>"""


def threshold_html(result: dict, violations: list[str], when: str) -> str:
    viol_rows = ""
    for v in violations:
        viol_rows += f"""\
<tr><td style="padding:10px 14px;background:rgba(255,90,90,0.08);border-left:3px solid {BAD};border-radius:6px;font-family:{SANS};font-size:14px;color:{TEXT};">{v}</td></tr>
<tr><td style="height:8px;font-size:0;">&nbsp;</td></tr>"""

    inner = f"""\
<tr><td style="padding:8px 28px 4px;">
  <h1 style="margin:0 0 6px;font-family:{SANS};font-size:22px;color:{TEXT};font-weight:bold;">
    &#9888;&#65039; Soglia superata
  </h1>
  <p style="margin:0 0 20px;font-family:{SANS};font-size:15px;color:{DIM};line-height:1.5;">
    La connessione &egrave; scesa sotto i valori attesi.
  </p>
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0">{viol_rows}</table>
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="margin-top:12px;">
    {_row("Server", result.get("server","?"), TEXT)}
    {_row("Orario", when, TEXT)}
  </table>
</td></tr>
<tr><td style="padding:20px 28px 8px;">
  <p style="margin:0;font-family:{SANS};font-size:13px;color:{DIM};font-style:italic;">
    Controlla la dashboard per i dettagli.
  </p>
</td></tr>"""
    return _shell(inner, accent=AMBER)


def failure_html(engine: str, error: str, when: str) -> str:
    inner = f"""\
<tr><td style="padding:8px 28px 4px;">
  <h1 style="margin:0 0 6px;font-family:{SANS};font-size:22px;color:{TEXT};font-weight:bold;">
    &#128308; Test fallito
  </h1>
  <p style="margin:0 0 20px;font-family:{SANS};font-size:15px;color:{DIM};line-height:1.5;">
    Il test di velocit&agrave; non &egrave; riuscito.
  </p>
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0">
    <tr><td style="padding:10px 14px;background:rgba(255,90,90,0.08);border-left:3px solid {BAD};border-radius:6px;font-family:{SANS};font-size:14px;color:{TEXT};">{error}</td></tr>
  </table>
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="margin-top:12px;">
    {_row("Motore", engine, TEXT)}
    {_row("Orario", when, TEXT)}
  </table>
</td></tr>
<tr><td style="padding:20px 28px 8px;">
  <p style="margin:0;font-family:{SANS};font-size:13px;color:{DIM};font-style:italic;">
    Se si ripete, potrebbe essere un'interruzione della linea.
  </p>
</td></tr>"""
    return _shell(inner, accent=BAD)


def _metric_card(label: str, avg: str, unit: str, mn: str, mx: str, color: str) -> str:
    return f"""\
<td width="33%" style="padding:6px;">
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:{BG};border:1px solid {EDGE};border-radius:10px;">
    <tr><td style="padding:14px 12px;">
      <div style="font-family:{MONO};font-size:10px;color:{DIM};text-transform:uppercase;letter-spacing:1px;">{label}</div>
      <div style="font-family:{MONO};font-size:24px;font-weight:bold;color:{color};margin-top:6px;">{avg}<span style="font-size:11px;color:{DIM};font-weight:normal;"> {unit}</span></div>
      <div style="font-family:{MONO};font-size:10px;color:{DIM};margin-top:6px;">min {mn} &middot; max {mx}</div>
    </td></tr>
  </table>
</td>"""


def report_html(stats: dict, outages: int, period_label: str,
                contract_pct: int | None, contract_mbps: int | None) -> str:
    dl, ul, pg = stats["download"], stats["upload"], stats["ping"]
    period_desc = "ultimi 7 giorni" if "settiman" in period_label else "ultimo mese"

    contract_block = ""
    if contract_pct is not None and contract_mbps:
        c = SIGNAL if contract_pct >= 80 else AMBER if contract_pct >= 60 else BAD
        bar_w = min(100, contract_pct)
        contract_block = f"""\
<tr><td style="padding:18px 28px 4px;">
  <div style="font-family:{MONO};font-size:11px;color:{DIM};text-transform:uppercase;letter-spacing:1px;margin-bottom:10px;">Rispetto del contratto</div>
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0"><tr>
    <td style="font-family:{MONO};font-size:30px;font-weight:bold;color:{c};width:90px;">{contract_pct}%</td>
    <td>
      <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:{BG};border:1px solid {EDGE};border-radius:7px;height:12px;">
        <tr><td style="width:{bar_w}%;background:{c};border-radius:7px;font-size:0;line-height:0;height:12px;">&nbsp;</td><td style="font-size:0;">&nbsp;</td></tr>
      </table>
      <div style="font-family:{MONO};font-size:11px;color:{DIM};margin-top:6px;">media {dl['avg']} Mbps su {contract_mbps} promessi</div>
    </td>
  </tr></table>
</td></tr>"""

    inner = f"""\
<tr><td style="padding:8px 28px 4px;">
  <h1 style="margin:0 0 4px;font-family:{SANS};font-size:22px;color:{TEXT};font-weight:bold;">
    &#128202; Report {period_label}
  </h1>
  <p style="margin:0 0 18px;font-family:{MONO};font-size:12px;color:{DIM};">Periodo: {period_desc}</p>
</td></tr>
<tr><td style="padding:0 22px;">
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0"><tr>
    {_metric_card("Download", str(dl['avg']), "Mbps", str(dl['min']), str(dl['max']), SIGNAL)}
    {_metric_card("Upload", str(ul['avg']), "Mbps", str(ul['min']), str(ul['max']), UPLOAD)}
    {_metric_card("Ping", str(pg['avg']), "ms", str(pg['min']), str(pg['max']), AMBER)}
  </tr></table>
</td></tr>
{contract_block}
<tr><td style="padding:18px 28px 8px;">
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0">
    {_row("Uptime", f"{stats['uptime_pct']}%", SIGNAL)}
    <tr><td colspan="2" style="font-family:{MONO};font-size:11px;color:{DIM};padding-bottom:8px;">{stats['failed_tests']} test falliti su {stats['total_tests']}</td></tr>
    {_row("Interruzioni", str(outages), AMBER if outages else TEXT)}
  </table>
</td></tr>"""
    return _shell(inner, accent=SIGNAL)
