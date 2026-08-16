"""
Motori di speedtest intercambiabili (Ookla / LibreSpeed).

Ogni engine espone:
  - run()        -> dict normalizzato con la misura
  - servers()    -> lista di server disponibili [{id, name, location, host}]

Il dict di run() e' sempre normalizzato:
  { download_mbps, upload_mbps, ping_ms, jitter_ms, packet_loss,
    server, server_id, engine }

Nessun metodo solleva verso il chiamante se non con SpeedtestError.
"""
from __future__ import annotations

import json
import shutil
import subprocess
from abc import ABC, abstractmethod


class SpeedtestError(RuntimeError):
    """Errore controllato durante una misura o l'elenco server."""


class BaseEngine(ABC):
    name: str = "base"

    def __init__(self, server_id: str | None = None):
        self.server_id = server_id

    @abstractmethod
    def run(self) -> dict: ...

    @abstractmethod
    def servers(self) -> list[dict]: ...

    @staticmethod
    def _bits_to_mbps(bits_per_sec: float) -> float:
        return round(bits_per_sec / 1_000_000, 2)

    @staticmethod
    def _require(binary: str) -> None:
        if shutil.which(binary) is None:
            raise SpeedtestError(
                f"Binario '{binary}' non trovato nel PATH. "
                f"Verifica l'installazione del motore."
            )


class OoklaEngine(BaseEngine):
    """Wrapper sul binario ufficiale Ookla `speedtest`."""

    name = "ookla"

    def __init__(self, server_id: str | None = None, binary: str = "speedtest"):
        super().__init__(server_id)
        self.binary = binary

    def run(self) -> dict:
        self._require(self.binary)
        cmd = [self.binary, "--format=json", "--accept-license", "--accept-gdpr"]
        if self.server_id:
            cmd += ["--server-id", str(self.server_id)]
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=180, check=True)
        except subprocess.TimeoutExpired as e:
            raise SpeedtestError("Timeout durante il test Ookla") from e
        except subprocess.CalledProcessError as e:
            raise SpeedtestError(f"Ookla ha fallito: {e.stderr.strip()[:200]}") from e

        try:
            data = json.loads(proc.stdout)
        except json.JSONDecodeError as e:
            raise SpeedtestError("Output Ookla non valido") from e

        ping = data.get("ping", {})
        server = data.get("server", {})
        pkt = data.get("packetLoss")
        return {
            "engine": self.name,
            "download_mbps": self._bits_to_mbps(data["download"]["bandwidth"] * 8),
            "upload_mbps": self._bits_to_mbps(data["upload"]["bandwidth"] * 8),
            "ping_ms": round(ping.get("latency", 0), 2) or None,
            "jitter_ms": round(ping.get("jitter", 0), 2) or None,
            "packet_loss": round(pkt, 2) if isinstance(pkt, (int, float)) else None,
            "server": f'{server.get("name", "?")} ({server.get("location", "?")})',
            "server_id": str(server.get("id")) if server.get("id") is not None else None,
        }

    def servers(self) -> list[dict]:
        self._require(self.binary)
        cmd = [self.binary, "--servers", "--format=json", "--accept-license", "--accept-gdpr"]
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=30, check=True)
            data = json.loads(proc.stdout)
        except (subprocess.SubprocessError, json.JSONDecodeError) as e:
            raise SpeedtestError(f"Impossibile elencare i server Ookla: {e}") from e
        out = []
        for s in data.get("servers", []):
            out.append({
                "id": str(s.get("id")),
                "name": s.get("name", "?"),
                "location": s.get("location", "") or s.get("country", ""),
                "host": s.get("host", ""),
            })
        return out


class LibreSpeedEngine(BaseEngine):
    """Wrapper sulla CLI `librespeed-cli` (open source, Go)."""

    name = "librespeed"

    def __init__(self, server_id: str | None = None, binary: str = "librespeed-cli"):
        super().__init__(server_id)
        self.binary = binary

    def run(self) -> dict:
        self._require(self.binary)
        cmd = [self.binary, "--json"]
        if self.server_id:
            cmd += ["--server", str(self.server_id)]
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=180, check=True)
        except subprocess.TimeoutExpired as e:
            raise SpeedtestError("Timeout durante il test LibreSpeed") from e
        except subprocess.CalledProcessError as e:
            raise SpeedtestError(f"LibreSpeed ha fallito: {e.stderr.strip()[:200]}") from e

        try:
            payload = json.loads(proc.stdout)
            data = payload[0] if isinstance(payload, list) else payload
        except (json.JSONDecodeError, IndexError) as e:
            raise SpeedtestError("Output LibreSpeed non valido") from e

        server = data.get("server", {})
        sname = server.get("name", "?") if isinstance(server, dict) else str(server)
        return {
            "engine": self.name,
            "download_mbps": round(float(data.get("download", 0)), 2),
            "upload_mbps": round(float(data.get("upload", 0)), 2),
            "ping_ms": round(float(data.get("ping", 0)), 2) or None,
            "jitter_ms": round(float(data.get("jitter", 0)), 2) or None,
            "packet_loss": None,
            "server": sname,
            "server_id": str(server.get("id")) if isinstance(server, dict) and server.get("id") is not None else None,
        }

    def servers(self) -> list[dict]:
        self._require(self.binary)
        cmd = [self.binary, "--list"]
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=30, check=True)
        except subprocess.SubprocessError as e:
            raise SpeedtestError(f"Impossibile elencare i server LibreSpeed: {e}") from e
        # --list restituisce righe testuali: "ID: Nome (Sponsor) [distanza]"
        out = []
        for line in proc.stdout.splitlines():
            line = line.strip()
            if not line or ":" not in line:
                continue
            sid, rest = line.split(":", 1)
            sid = sid.strip()
            if not sid.isdigit():
                continue
            out.append({"id": sid, "name": rest.strip(), "location": "", "host": ""})
        return out


ENGINES = {OoklaEngine.name: OoklaEngine, LibreSpeedEngine.name: LibreSpeedEngine}


def build_engine(name: str, server_id: str | None = None) -> BaseEngine:
    cls = ENGINES.get(name)
    if cls is None:
        raise SpeedtestError(f"Engine sconosciuto: {name}")
    return cls(server_id=server_id)
