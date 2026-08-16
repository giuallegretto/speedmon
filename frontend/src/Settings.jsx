import React, { useState } from "react";
import { api } from "./api";

// Pannello impostazioni. Riceve i settings correnti e un callback onSaved.
export default function Settings({ settings, onSaved, onRunTest }) {
  const [s, setS] = useState(settings);
  const [servers, setServers] = useState(null);
  const [loadingServers, setLoadingServers] = useState(false);
  const [saved, setSaved] = useState(false);
  const [err, setErr] = useState(null);
  const [running, setRunning] = useState(false);

  // aggiornatori immutabili annidati
  const set = (path, val) => {
    setS((prev) => {
      const next = structuredClone(prev);
      let o = next;
      for (let i = 0; i < path.length - 1; i++) o = o[path[i]];
      o[path[path.length - 1]] = val;
      return next;
    });
  };

  const findServers = async () => {
    setLoadingServers(true); setErr(null);
    try { setServers(await api.servers()); }
    catch (e) { setErr(`Impossibile elencare i server: ${e.message}`); }
    finally { setLoadingServers(false); }
  };

  const save = async () => {
    setErr(null);
    try {
      const fresh = await api.saveSettings(s);
      setS(fresh); onSaved?.(fresh);
      setSaved(true); setTimeout(() => setSaved(false), 1800);
    } catch (e) { setErr(`Salvataggio fallito: ${e.message}`); }
  };

  const testNotify = async (ch) => {
    setErr(null);
    try { await api.testNotify(ch); alert(`${ch}: notifica di prova inviata`); }
    catch (e) { setErr(`Test ${ch} fallito: ${e.message}`); }
  };

  const runTest = async () => {
    setRunning(true); setErr(null);
    try { await onRunTest?.(); }
    catch (e) { setErr(e.message); }
    finally { setRunning(false); }
  };

  const bands = s.hourly_bands || [];
  const setBand = (i, k, v) => set(["hourly_bands", i, k], v);
  const addBand = () => bands.length < 4 && setS((p) => ({
    ...p, hourly_bands: [...p.hourly_bands, { name: "Nuova", from: "00:00", to: "06:00", download_min: 500 }],
  }));
  const rmBand = (i) => setS((p) => ({ ...p, hourly_bands: p.hourly_bands.filter((_, j) => j !== i) }));

  const email = s.notify?.email || {};
  const tg = s.notify?.telegram || {};
  const report = s.report || {};

  return (
    <div>
      {err && <div className="err">{err}</div>}

      <div className="card">
        <h2>Test manuale</h2>
        <p className="desc">Lancia una misura adesso, fuori dallo scheduler.</p>
        <div className="run-box">
          <button className="btn" onClick={runTest} disabled={running}>
            {running ? "misura in corso…" : "▶ Lancia test ora"}
          </button>
          {running && <div className="live"><span className="spinner" /> attendere…</div>}
        </div>
      </div>

      <div className="card">
        <h2>Contratto &amp; scheduler</h2>
        <p className="desc">La velocità promessa dall'ISP alimenta il calcolo "% erogata".</p>
        <div className="two">
          <div className="field"><label>Download promesso (Mbps)</label>
            <input type="number" value={s.contract_download ?? ""} placeholder="es. 1000"
              onChange={(e) => set(["contract_download"], Number(e.target.value) || 0)} /></div>
          <div className="field"><label>Motore</label>
            <select value={s.engine} onChange={(e) => { set(["engine"], e.target.value); setServers(null); }}>
              <option value="ookla">Ookla</option>
              <option value="librespeed">LibreSpeed</option>
            </select></div>
          <div className="field"><label>Intervallo (minuti)</label>
            <input type="number" value={s.interval_min}
              onChange={(e) => set(["interval_min"], Number(e.target.value) || 60)} /></div>
        </div>
        <div className="field">
          <label>Server</label>
          <select value={s.server_id ?? ""} onChange={(e) => set(["server_id"], e.target.value || null)}>
            <option value="">Automatico (più vicino)</option>
            {(servers || []).map((sv) => (
              <option key={sv.id} value={sv.id}>{sv.id} · {sv.name}{sv.location ? ` (${sv.location})` : ""}</option>
            ))}
            {s.server_id && !(servers || []).some((sv) => sv.id === s.server_id) && (
              <option value={s.server_id}>Bloccato: {s.server_id}</option>
            )}
          </select>
          <button className="btn ghost small" style={{ marginTop: 10 }} onClick={findServers} disabled={loadingServers}>
            {loadingServers ? "ricerca…" : "Trova server disponibili"}
          </button>
          <p className="desc" style={{ marginTop: 8, marginBottom: 0 }}>
            Bloccare un server rende i dati confrontabili nel tempo. In automatico il motore sceglie il più vicino a ogni test.
          </p>
        </div>
      </div>

      <div className="card">
        <h2>Soglie orarie a fasce</h2>
        <p className="desc">Soglie diverse per fascia oraria. Fino a 4 fasce; fuori dalle fasce vale la soglia globale.</p>
        <div className="band-head"><span>Fascia</span><span>Da</span><span>A</span><span>Down min</span><span /></div>
        {bands.map((b, i) => (
          <div className="band-row" key={i}>
            <div className="field"><input type="text" value={b.name} onChange={(e) => setBand(i, "name", e.target.value)} /></div>
            <div className="field"><input type="time" value={b.from} onChange={(e) => setBand(i, "from", e.target.value)} /></div>
            <div className="field"><input type="time" value={b.to} onChange={(e) => setBand(i, "to", e.target.value)} /></div>
            <div className="field"><input type="number" value={b.download_min} onChange={(e) => setBand(i, "download_min", Number(e.target.value) || 0)} /></div>
            <button className="rm" onClick={() => rmBand(i)}>✕</button>
          </div>
        ))}
        {bands.length < 4 && <button className="btn ghost small" onClick={addBand}>+ Aggiungi fascia</button>}
        <div className="two" style={{ marginTop: 18 }}>
          <div className="field"><label>Soglia globale download</label>
            <input type="number" value={s.thresholds?.download ?? ""} onChange={(e) => set(["thresholds", "download"], Number(e.target.value) || 0)} /></div>
          <div className="field"><label>Upload min (Mbps)</label>
            <input type="number" value={s.thresholds?.upload ?? ""} onChange={(e) => set(["thresholds", "upload"], Number(e.target.value) || 0)} /></div>
          <div className="field"><label>Ping max (ms)</label>
            <input type="number" value={s.thresholds?.ping ?? ""} onChange={(e) => set(["thresholds", "ping"], Number(e.target.value) || 0)} /></div>
        </div>
      </div>

      <div className="card">
        <h2>Report periodico</h2>
        <p className="desc">Riepilogo automatico via email con medie, uptime e interruzioni.</p>
        <div className="toggle-row first">
          <div className="toggle-label"><b>Invia report</b><small>riepilogo ricorrente</small></div>
          <label className="switch"><input type="checkbox" checked={!!report.enabled} onChange={(e) => set(["report", "enabled"], e.target.checked)} /><span className="slider" /></label>
        </div>
        {report.enabled && (
          <div className="collapse">
            <div className="two">
              <div className="field"><label>Frequenza</label>
                <select value={report.frequency} onChange={(e) => set(["report", "frequency"], e.target.value)}>
                  <option value="weekly">Settimanale (lunedì)</option>
                  <option value="monthly">Mensile (giorno 1)</option>
                </select></div>
              <div className="field"><label>Ora invio</label>
                <input type="time" value={report.time} onChange={(e) => set(["report", "time"], e.target.value)} /></div>
            </div>
            <div className="field"><label>Destinatario</label>
              <input type="email" value={report.to || ""} onChange={(e) => set(["report", "to"], e.target.value)} /></div>
          </div>
        )}
      </div>

      <div className="card">
        <h2>Notifiche</h2>
        <p className="desc">Avviso quando una soglia viene superata o un test fallisce.</p>
        <div className="toggle-row first">
          <div className="toggle-label"><b>Email</b><small>invio tramite SMTP</small></div>
          <label className="switch"><input type="checkbox" checked={!!email.enabled} onChange={(e) => set(["notify", "email", "enabled"], e.target.checked)} /><span className="slider" /></label>
        </div>
        {email.enabled && (
          <div className="collapse">
            <div className="field"><label>Destinatario</label>
              <input type="email" value={email.to || ""} onChange={(e) => set(["notify", "email", "to"], e.target.value)} /></div>
            <div className="two">
              <div className="field"><label>Server SMTP</label>
                <input type="text" value={email.smtp_host || ""} onChange={(e) => set(["notify", "email", "smtp_host"], e.target.value)} /></div>
              <div className="field"><label>Porta</label>
                <input type="number" value={email.smtp_port || 587} onChange={(e) => set(["notify", "email", "smtp_port"], Number(e.target.value) || 587)} /></div>
            </div>
            <div className="two">
              <div className="field"><label>Utente</label>
                <input type="text" value={email.smtp_user || ""} onChange={(e) => set(["notify", "email", "smtp_user"], e.target.value)} /></div>
              <div className="field"><label>App password</label>
                <input type="password" value={email.smtp_pass || ""} onChange={(e) => set(["notify", "email", "smtp_pass"], e.target.value)} /></div>
            </div>
            <button className="btn ghost small" onClick={() => testNotify("email")}>Invia email di prova</button>
          </div>
        )}
        <div className="toggle-row">
          <div className="toggle-label"><b>Telegram</b><small>tramite bot personale</small></div>
          <label className="switch"><input type="checkbox" checked={!!tg.enabled} onChange={(e) => set(["notify", "telegram", "enabled"], e.target.checked)} /><span className="slider" /></label>
        </div>
        {tg.enabled && (
          <div className="collapse">
            <div className="field"><label>Bot token</label>
              <input type="text" value={tg.bot_token || ""} onChange={(e) => set(["notify", "telegram", "bot_token"], e.target.value)} /></div>
            <div className="field"><label>Chat ID</label>
              <input type="text" value={tg.chat_id || ""} onChange={(e) => set(["notify", "telegram", "chat_id"], e.target.value)} /></div>
            <button className="btn ghost small" onClick={() => testNotify("telegram")}>Invia messaggio di prova</button>
          </div>
        )}
      </div>

      <div className="save-bar">
        {saved && <span className="saved">✓ impostazioni salvate</span>}
        <button className="btn" onClick={save}>Salva impostazioni</button>
      </div>
    </div>
  );
}
