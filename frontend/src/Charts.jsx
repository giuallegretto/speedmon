import React from "react";
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  BarChart, Bar, Cell, ReferenceLine, ReferenceArea, Scatter, ComposedChart,
} from "recharts";
import { COL, fmtAxis, fmtFull } from "./api";

function TipBox({ active, payload, kind }) {
  if (!active || !payload?.length) return null;
  const p = payload[0].payload;
  return (
    <div style={{ background: "#0d1420", border: `1px solid ${COL.edge}`, borderRadius: 8,
      padding: "8px 11px", fontFamily: COL.mono, fontSize: 11 }}>
      <div style={{ color: COL.dim, marginBottom: 5 }}>{fmtFull(p.ts)}</div>
      {p.failed ? (
        <div style={{ color: COL.bad }}>✕ test fallito</div>
      ) : kind === "ping" ? (
        <div style={{ display: "flex", justifyContent: "space-between", gap: 14 }}>
          <span>ping</span><b style={{ color: COL.amber }}>{p.ping} ms</b>
        </div>
      ) : (
        <>
          <div style={{ display: "flex", justifyContent: "space-between", gap: 14 }}>
            <span style={{ color: COL.signal }}>down</span><b>{p.download}</b></div>
          <div style={{ display: "flex", justifyContent: "space-between", gap: 14 }}>
            <span style={{ color: COL.upload }}>up</span><b>{p.upload}</b></div>
        </>
      )}
    </div>
  );
}

// prepara i dati: aggiunge label asse e marca i fail
function prep(results, hours) {
  return results.map((r) => ({
    ts: r.ts,
    label: fmtAxis(r.ts, hours),
    download: r.download_mbps,
    upload: r.upload_mbps,
    ping: r.ping_ms,
    failed: r.ok === 0,
    failMark: r.ok === 0 ? 0 : null, // per lo scatter sull'asse
  }));
}

export function BandChart({ results, hours, threshold }) {
  const data = prep(results, hours);
  // segmenti sotto soglia -> aree rosse
  return (
    <ResponsiveContainer width="100%" height={260}>
      <ComposedChart data={data} margin={{ top: 6, right: 10, left: -8, bottom: 0 }}>
        <CartesianGrid stroke={COL.grid} strokeDasharray="3 3" vertical={false} />
        <XAxis dataKey="label" stroke={COL.dim} tick={{ fontSize: 9, fontFamily: COL.mono }} minTickGap={40} />
        <YAxis stroke={COL.dim} tick={{ fontSize: 10, fontFamily: COL.mono }} />
        <Tooltip content={<TipBox kind="band" />} />
        {threshold ? <ReferenceLine y={threshold} stroke={COL.amber} strokeDasharray="5 4" strokeWidth={1.5} /> : null}
        <Line type="monotone" dataKey="download" stroke={COL.signal} strokeWidth={2} dot={false} connectNulls={false} isAnimationActive={false} />
        <Line type="monotone" dataKey="upload" stroke={COL.upload} strokeWidth={2} dot={false} connectNulls={false} isAnimationActive={false} />
        <Scatter dataKey="failMark" fill={COL.bad} shape="cross" isAnimationActive={false} />
      </ComposedChart>
    </ResponsiveContainer>
  );
}

export function PingChart({ results, hours }) {
  const data = prep(results, hours);
  return (
    <ResponsiveContainer width="100%" height={180}>
      <LineChart data={data} margin={{ top: 6, right: 10, left: -8, bottom: 0 }}>
        <CartesianGrid stroke={COL.grid} strokeDasharray="3 3" vertical={false} />
        <XAxis dataKey="label" stroke={COL.dim} tick={{ fontSize: 9, fontFamily: COL.mono }} minTickGap={40} />
        <YAxis stroke={COL.dim} tick={{ fontSize: 10, fontFamily: COL.mono }} />
        <Tooltip content={<TipBox kind="ping" />} />
        <Line type="monotone" dataKey="ping" stroke={COL.amber} strokeWidth={2} dot={false} connectNulls={false} isAnimationActive={false} />
      </LineChart>
    </ResponsiveContainer>
  );
}

export function HourlyChart({ hourly, avg }) {
  const data = hourly.map((h) => ({ hour: h.hour, avg: h.avg_down }));
  return (
    <ResponsiveContainer width="100%" height={180}>
      <BarChart data={data} margin={{ top: 6, right: 6, left: -8, bottom: 0 }}>
        <CartesianGrid stroke={COL.grid} strokeDasharray="3 3" vertical={false} />
        <XAxis dataKey="hour" stroke={COL.dim} tick={{ fontSize: 9, fontFamily: COL.mono }} interval={2} />
        <YAxis stroke={COL.dim} tick={{ fontSize: 10, fontFamily: COL.mono }} />
        <Tooltip content={({ active, payload }) => active && payload?.length ? (
          <div style={{ background: "#0d1420", border: `1px solid ${COL.edge}`, borderRadius: 8, padding: "8px 11px", fontFamily: COL.mono, fontSize: 11 }}>
            ore {payload[0].payload.hour}:00 · <b>{payload[0].value} Mbps</b>
          </div>) : null} />
        {avg ? <ReferenceLine y={avg} stroke={COL.signal} strokeDasharray="4 4" /> : null}
        <Bar dataKey="avg" radius={[3, 3, 0, 0]} isAnimationActive={false}>
          {data.map((d, i) => (
            <Cell key={i} fill={d.avg && avg && d.avg < avg * 0.75 ? COL.amber : COL.upload} />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}

export function Sparkline({ results }) {
  const pts = results.filter((r) => r.download_mbps != null).slice(0, 10).reverse();
  const data = pts.map((r, i) => ({ i, v: r.download_mbps }));
  if (!data.length) return null;
  return (
    <ResponsiveContainer width={120} height={30}>
      <LineChart data={data}>
        <Line type="monotone" dataKey="v" stroke={COL.signal} strokeWidth={1.5} dot={false} isAnimationActive={false} />
      </LineChart>
    </ResponsiveContainer>
  );
}
