from __future__ import annotations

import json
import subprocess
import threading
import time
import urllib.request


class NgrokManager:
    def __init__(self) -> None:
        self._proc: subprocess.Popen | None = None
        self.public_url: str | None = None
        self.callback_url: str | None = None
        self.local_port: int | None = None
        self.last_error: str | None = None

    def status(self) -> dict:
        running = self._proc is not None and self._proc.poll() is None
        return {
            "running": running,
            "publicUrl": self.public_url,
            "callbackUrl": self.callback_url,
            "localPort": self.local_port,
            "lastError": self.last_error,
        }

    def stop(self) -> dict:
        proc = self._proc
        self._proc = None
        if proc is not None and proc.poll() is None:
            try:
                proc.terminate()
                proc.wait(timeout=5)
            except Exception:
                try:
                    proc.kill()
                except Exception:
                    pass
        self.public_url = None
        self.callback_url = None
        self.local_port = None
        return self.status()

    def _fetch_public_url(self, web_port: int = 4040) -> str | None:
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{web_port}/api/tunnels", timeout=2) as response:
                raw = response.read().decode("utf-8", errors="replace")
            payload = json.loads(raw)
            urls = []
            for item in list(payload.get("tunnels") or []):
                if isinstance(item, dict):
                    url = str(item.get("public_url", "")).strip()
                    if url:
                        urls.append(url)
            for url in urls:
                if url.startswith("https://"):
                    return url
            return urls[0] if urls else None
        except Exception:
            return None

    def start(self, *, ngrok_path: str | None = None, local_port: int, callback_path: str = "/suno/callback") -> dict:
        if self._proc is not None and self._proc.poll() is None:
            return self.status()
        self.last_error = None
        self.public_url = None
        self.callback_url = None
        self.local_port = int(local_port)
        callback_path = callback_path if str(callback_path or "").startswith("/") else f"/{callback_path}"
        exec_path = str(ngrok_path or "ngrok").strip() or "ngrok"
        web_port = 4040

        try:
            proc = subprocess.Popen(
                [exec_path, "http", str(local_port), "--log=stdout", "--log-format=json", "--web-addr", f"127.0.0.1:{web_port}"],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                stdin=subprocess.DEVNULL,
                text=True,
                encoding="utf-8",
                errors="replace",
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
        except Exception as exc:
            self.last_error = str(exc)
            return self.status()

        self._proc = proc

        def read_lines():
            try:
                assert proc.stdout is not None
                for line in proc.stdout:
                    line = str(line or "").strip()
                    if not line:
                        continue
                    try:
                        payload = json.loads(line)
                    except Exception:
                        continue
                    msg = str(payload.get("msg", "")).strip()
                    url = str(payload.get("url", "")).strip()
                    err = str(payload.get("err", "")).strip()
                    if err:
                        self.last_error = err
                    if not self.public_url and url and "started tunnel" in msg.lower():
                        self.public_url = url
                        self.callback_url = f"{url}{callback_path}"
            except Exception as exc:
                self.last_error = str(exc)

        threading.Thread(target=read_lines, daemon=True).start()

        started_at = time.time()
        while time.time() - started_at < 12:
            if self.last_error:
                break
            if self.public_url:
                break
            from_api = self._fetch_public_url(web_port)
            if from_api:
                self.public_url = from_api
                self.callback_url = f"{from_api}{callback_path}"
                break
            time.sleep(0.2)
        return self.status()
