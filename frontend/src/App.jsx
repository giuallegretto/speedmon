import React, { useState, useEffect, useCallback, useMemo } from "react";
import "./styles.css";
import { api, COL, fmtFull } from "./api";
import { BandChart, PingChart, HourlyChart, Sparkline } from "./Charts";
import Settings from "./Settings";

const RANGES = [{ label: "24H", h: 24 }, { label: "7G", h: 168 }, { label: "30G", h: 720 }];
const AUTHOR = "Giuseppe Allegretto"; // <-- personalizzato in fase di build

function Delta({ value, inverse }) {
  if (value == null) return null;
  const good = inverse ? value < 0 : value > 0;
  const arrow = value >= 0 ? "▲" : "▼";
  return <div className={`delta ${good ? "up-g" : "down-r"}`}>{arrow} {Math.abs(value)}% vs periodo prec.</div>;
}

export default function App() {
  const [tab, setTab] = useState("dash");
  const [range, setRange] = useState(RANGES[0]);
  const [results, setResults] = useState([]);
  const [stats, setStats] = useState(null);
  const [hourly, setHourly] = useState([]);
  const [outages, setOutages] = useState([]);
  const [settings, setSettings] = useState(null);
  const [err, setErr] = useState(null);
  const [quickRunning, setQuickRunning] = useState(false);

  const loadData = useCallback(async () => {
    try {
      setErr(null);
      const [r, s, h, o] = await Promise.all([
        api.results(range.h), api.stats(range.h),
        api.hourly(Math.max(range.h, 168)), api.outages(range.h),
      ]);
      setResults(r); setStats(s); setHourly(h); setOutages(o);
    } catch (e) { setErr(e.message); }
  }, [range]);

  useEffect(() => { api.getSettings().then(setSettings).catch((e) => setErr(e.message)); }, []);
  useEffect(() => {
    loadData();
    const id = setInterval(loadData, 60000);
    return () => clearInterval(id);
  }, [loadData]);

  const runNow = useCallback(async () => {
    await api.runNow();
    await loadData();
  }, [loadData]);

  const quickRun = async () => {
    setQuickRunning(true);
    try { await runNow(); } catch (e) { setErr(e.message); } finally { setQuickRunning(false); }
  };

  // ordine: API torna DESC (recenti prima); i grafici vogliono ASC
  const asc = useMemo(() => [...results].reverse(), [results]);
  const last = useMemo(() => results.find((r) => r.ok === 1), [results]);
  const contract = settings?.contract_download;
  const threshold = settings?.thresholds?.download;

  const contractPct = contract && stats?.download?.avg
    ? Math.min(100, Math.round(stats.download.avg / contract * 100)) : null;
  const contractColor = contractPct == null ? COL.dim
    : contractPct >= 80 ? COL.signal : contractPct >= 60 ? COL.amber : COL.bad;

  return (
    <div className="wrap">
      <div className="top">
        <div className="brand">
          <img src="/icon.svg" alt="SpeedMon" />
          <div>
            <h1>SpeedMon</h1>
            <div className="who">
              {settings ? `engine: ${settings.engine} · ogni ${settings.interval_min} min` : "…"}
            </div>
          </div>
        </div>
        <div className="tabs">
          {["dash", "hist", "set"].map((t) => (
            <button key={t} className={tab === t ? "active" : ""} onClick={() => setTab(t)}>
              {t === "dash" ? "Dashboard" : t === "hist" ? "Storico" : "Impostazioni"}
            </button>
          ))}
        </div>
      </div>

      {err && <div className="err">Errore: {err}</div>}

      {tab === "dash" && (
        <>
          <div className="hero">
            <div>
              <div className="big" style={{ color: last && contract && last.download_mbps >= (threshold || 0) ? COL.signal : COL.amber }}>
                {last ? Math.round(last.download_mbps) : "—"}<small>Mbps ↓</small>
              </div>
              {last && (
                <span className={`state ${last.download_mbps >= (threshold || 0) ? "st-ok" : "st-warn"}`}>
                  {last.download_mbps >= (threshold || 0) ? "✓ sopra soglia" : "⚠ sotto soglia"}
                </span>
              )}
            </div>
            <div className="sep" />
            <div className="meta">
              <div className="lbl">Upload</div>
              <div className="metric"><b className="c-up">{last ? Math.round(last.upload_mbps) : "—"}</b> Mbps ↑</div>
              <div className="lbl" style={{ marginTop: 6 }}>Ping</div>
              <div className="metric"><b className="c-ping">{last ? last.ping_ms : "—"}</b> ms</div>
            </div>
            <div className="sep" />
            <div>
              <div className="lbl" style={{ marginBottom: 4 }}>ultime 10 misure</div>
              <Sparkline results={results} />
            </div>
            <div className="when">
              <div className="lbl">Ultimo test</div>
              <div style={{ color: COL.text, fontSize: 13, marginTop: 4 }}>{last ? fmtFull(last.ts) : "—"}</div>
              <div style={{ marginTop: 4 }}>{last?.server || ""}</div>
              <button className="btn" style={{ marginTop: 12 }} onClick={quickRun} disabled={quickRunning}>
                {quickRunning ? "misura in corso…" : "▶ Lancia test ora"}
              </button>
            </div>
          </div>

          <div className="card">
            <h2>Rispetto del contratto</h2>
            <div className="contract">
              <div className="pct" style={{ color: contractColor }}>{contractPct != null ? `${contractPct}%` : "—"}</div>
              <div className="bardock">
                <div className="barbg"><div className="barfill" style={{ width: `${contractPct || 0}%`, background: contractColor }} /></div>
                <div className="barlabels">
                  <span>media {stats?.download?.avg ?? "—"} Mbps</span>
                  <span>{contract ? `promesso ${contract} Mbps` : "imposta la velocità contrattuale"}</span>
                </div>
              </div>
            </div>
          </div>

          <div className="controls">
            <div className="ranges">
              {RANGES.map((r) => (
                <button key={r.label} className={range.label === r.label ? "active" : ""} onClick={() => setRange(r)}>{r.label}</button>
              ))}
            </div>
            <button className="btn ghost small" onClick={quickRun} disabled={quickRunning}>
              {quickRunning ? "… in corso" : "▶ test ora"}
            </button>
          </div>

          <div className="kpis">
            <div className="kpi"><div className="lbl">Download medio</div>
              <div className="val" style={{ color: COL.signal }}>{stats?.download?.avg ?? "—"}</div>
              <div className="sub">min {stats?.download?.min ?? "—"} · max {stats?.download?.max ?? "—"}</div>
              <Delta value={stats?.delta_download_pct} /></div>
            <div className="kpi"><div className="lbl">Upload medio</div>
              <div className="val" style={{ color: COL.upload }}>{stats?.upload?.avg ?? "—"}</div>
              <div className="sub">min {stats?.upload?.min ?? "—"} · max {stats?.upload?.max ?? "—"}</div></div>
            <div className="kpi"><div className="lbl">Ping medio</div>
              <div className="val" style={{ color: COL.amber }}>{stats?.ping?.avg ?? "—"}</div>
              <div className="sub">min {stats?.ping?.min ?? "—"} · max {stats?.ping?.max ?? "—"}</div></div>
            <div className="kpi"><div className="lbl">Uptime</div>
              <div className="val">{stats?.uptime_pct ?? "—"}</div>
              <div className="sub">{stats?.failed_tests ?? 0} falliti su {stats?.total_tests ?? 0}</div></div>
          </div>

          <div className="card">
            <div className="chart-lbl">Banda · Mbps</div>
            <BandChart results={asc} hours={range.h} threshold={threshold} />
            <div className="legend">
              <span><span className="swatch" style={{ background: COL.signal }} />download</span>
              <span><span className="swatch" style={{ background: COL.upload }} />upload</span>
              <span><span className="swatch dash" />soglia min{threshold ? ` (${threshold})` : ""}</span>
              <span style={{ color: COL.bad }}>✕ test fallito</span>
            </div>
          </div>

          <div className="grid2">
            <div className="card">
              <div className="chart-lbl">Latenza · ms</div>
              <PingChart results={asc} hours={range.h} />
            </div>
            <div className="card">
              <div className="chart-lbl">Download medio per ora del giorno</div>
              <HourlyChart hourly={hourly} avg={stats?.download?.avg} />
            </div>
          </div>

          <div className="card">
            <h2>Interruzioni rilevate</h2>
            <p className="desc">Sequenze di test falliti consecutivi, raggruppate come singolo evento.</p>
            {outages.length === 0 ? (
              <div style={{ color: COL.dim, fontFamily: COL.mono, fontSize: 12 }}>Nessuna interruzione nel periodo. 👍</div>
            ) : outages.map((o, i) => (
              <div className="outage" key={i}>
                <span className="oic">●</span>
                <span>{fmtFull(o.from)} → {new Date(o.to).toLocaleTimeString("it-IT", { hour: "2-digit", minute: "2-digit" })}</span>
                <span style={{ color: COL.dim }}>{o.count} test falliti</span>
                <span className="odur">{o.duration_min} min</span>
              </div>
            ))}
          </div>
        </>
      )}

      {tab === "hist" && (
        <>
          <div className="controls">
            <div className="ranges">
              {RANGES.map((r) => (
                <button key={r.label} className={range.label === r.label ? "active" : ""} onClick={() => setRange(r)}>{r.label}</button>
              ))}
            </div>
            <a className="btn ghost small" href={`/api/export?hours=${range.h}`} style={{ textDecoration: "none" }}>↓ Esporta JSON</a>
          </div>
          <div className="card">
            <h2>Misure recenti</h2>
            <table>
              <thead><tr><th>Data / ora</th><th>Download</th><th>Upload</th><th>Ping</th><th>Server</th><th>Esito</th></tr></thead>
              <tbody>
                {results.slice(0, 100).map((r) => {
                  const under = r.ok === 1 && threshold && r.download_mbps < threshold;
                  const cls = r.ok === 0 ? "row-fail" : under ? "row-warn" : "";
                  return (
                    <tr key={r.id} className={cls}>
                      <td>{fmtFull(r.ts)}</td>
                      <td className="c-down">{r.download_mbps ?? "—"}</td>
                      <td className="c-up">{r.upload_mbps ?? "—"}</td>
                      <td className="c-ping">{r.ping_ms ?? "—"}</td>
                      <td>{r.server || "—"}</td>
                      <td>{r.ok === 0 ? <span className="badge fail">FALLITO</span> : under ? <span className="badge warn">SOTTO SOGLIA</span> : <span className="badge ok">OK</span>}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </>
      )}

      {tab === "set" && settings && (
        <Settings settings={settings} onSaved={setSettings} onRunTest={runNow} />
      )}

      <div className="foot">
        Creato da {AUTHOR}<br />
        SpeedMon · self-hosted
      </div>
    </div>
  );
}
