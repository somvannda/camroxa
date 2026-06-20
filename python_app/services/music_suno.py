from __future__ import annotations

import hashlib
import json
import os
import re
import urllib.request
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from python_app.services.generation_proxy import GenerationProxy


def hash_suno_generate_request(*, model: str, title: str, prompt: str, style: str, instrumental: bool) -> str:
    normalized = {
        "model": str(model or "").strip(),
        "title": str(title or "").strip(),
        "prompt": str(prompt or "").strip(),
        "style": str(style or "").strip(),
        "instrumental": bool(instrumental),
    }
    return hashlib.sha256(json.dumps(normalized, ensure_ascii=False).encode("utf-8")).hexdigest()


def _base_http_headers() -> dict[str, str]:
    return {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "en-US,en;q=0.9",
    }


def suno_api_generate(*, generation_proxy: GenerationProxy, model: str, title: str, lyrics: str, style: str, instrumental: bool) -> dict:
    """Submit music generation to Suno via the Platform API.

    Returns dict with key 'taskId' containing the task identifier string.
    """
    task_id = generation_proxy.submit_suno(
        model=model,
        title=title,
        lyrics=lyrics,
        style=style,
        instrumental=instrumental,
    )
    return {"taskId": task_id}


def suno_api_try_get_tracks(generation_proxy: GenerationProxy, task_id: str) -> dict:
    """Poll Suno task status via the Platform API.

    Returns dict with keys: 'status', 'audioUrls' (list of up to 2 URLs).
    """
    result = generation_proxy.get_suno_status(task_id)
    return {
        "status": str(result.get("status", "PENDING")).strip() or "PENDING",
        "audioUrls": list(result.get("audioUrls") or [])[:2],
    }


def download_to_file(url: str, out_path: str) -> str:
    path = Path(out_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    req = urllib.request.Request(str(url), headers=_base_http_headers(), method="GET")
    try:
        with urllib.request.urlopen(req, timeout=120) as response:
            data = response.read()
    except Exception as exc:
        raise RuntimeError(f"Download failed: {exc}") from exc
    path.write_bytes(data)
    return str(path)


def _sanitize_file_name(value: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r'[\\/:*?"<>|]', "_", str(value or ""))).strip()[:120]


def build_suno_output_paths(*, output_dir: str, title: str, track_no: int | None = None) -> dict[str, str]:
    base = _sanitize_file_name(title)
    prefix = f"{max(1, int(track_no))}. " if isinstance(track_no, int) else ""
    return {
        "ok": str(Path(output_dir) / f"{prefix}{base}_OK.mp3"),
        "alt": str(Path(output_dir) / f"{prefix}{base}_Alt.mp3"),
    }


def _sanitize_folder_segment(value: str) -> str:
    return re.sub(r"\s", "-", re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 _.-]+", "", str(value or "").lower())).strip())[:48]


def _sanitize_run_label(value: str) -> str:
    return re.sub(r"\s", "-", re.sub(r"\s+", " ", re.sub(r"[^a-zA-Z0-9 _.-]+", "", str(value or ""))).strip())[:64]


def plan_next_run_dir(base_dir: str, profile_folder_name: str, prefix: str) -> str:
    base = str(base_dir or "").strip()
    if not base:
        raise RuntimeError("Suno output directory is not configured")
    profile_dir = Path(base) / (_sanitize_folder_segment(profile_folder_name) or "profile")
    profile_dir.mkdir(parents=True, exist_ok=True)
    entries = [child.name for child in profile_dir.iterdir() if child.is_dir()] if profile_dir.exists() else []
    max_n = 0
    for name in entries:
        match = re.match(r"^(?:.*_)?(\d{2,})$", str(name))
        if match:
            max_n = max(max_n, int(match.group(1)))
    clean_prefix = (_sanitize_folder_segment(prefix) or "").replace("-", "_")
    for n in range(max_n + 1, max_n + 10000):
        suffix = str(n).zfill(2)
        folder_name = f"{clean_prefix}_{suffix}" if clean_prefix else suffix
        run_dir = profile_dir / folder_name
        try:
            run_dir.mkdir(parents=False, exist_ok=False)
            return str(run_dir)
        except FileExistsError:
            continue
    raise RuntimeError("Failed to allocate a new run folder")


def plan_next_paired_run_dirs_by_label(base_dir: str, ok_profile_folder_name: str, alt_profile_folder_name: str | None, label: str) -> dict[str, str]:
    base = str(base_dir or "").strip()
    if not base:
        raise RuntimeError("Suno output directory is not configured")
    ok_profile_dir = Path(base) / (_sanitize_folder_segment(ok_profile_folder_name) or "profile")
    alt_profile_dir = Path(base) / (_sanitize_folder_segment(alt_profile_folder_name) or _sanitize_folder_segment(ok_profile_folder_name) or "profile")
    ok_profile_dir.mkdir(parents=True, exist_ok=True)
    alt_profile_dir.mkdir(parents=True, exist_ok=True)
    base_name = _sanitize_run_label(label) or "run"
    ok_entries = [child.name for child in ok_profile_dir.iterdir() if child.is_dir()]
    alt_entries = [child.name for child in alt_profile_dir.iterdir() if child.is_dir()]
    pattern = re.compile(rf"^{re.escape(base_name)}_(\d{{2,}})$")

    def get_max_index(entries: list[str]) -> int:
        max_n = 1 if base_name in entries else 0
        for name in entries:
            match = pattern.match(name)
            if match:
                max_n = max(max_n, int(match.group(1)))
        return max_n

    max_both = max(get_max_index(ok_entries), get_max_index(alt_entries))
    run_folder_name = base_name if max_both == 0 else f"{base_name}_{str(max_both + 1).zfill(2)}"
    ok_run_dir = ok_profile_dir / run_folder_name
    alt_run_dir = alt_profile_dir / run_folder_name
    ok_run_dir.mkdir(parents=False, exist_ok=False)
    if alt_run_dir != ok_run_dir:
        alt_run_dir.mkdir(parents=False, exist_ok=False)
    return {"okRunDir": str(ok_run_dir), "altRunDir": str(alt_run_dir)}


def poll_and_download_pending_suno(
    *,
    db_cfg: Any,
    generation_proxy: GenerationProxy,
    output_dir: str,
    max_tasks_per_run: int = 10,
    list_pending_tasks: Any,
    upsert_suno_task: Any,
    list_songs_by_batch_id: Any,
) -> dict:
    output_dir = str(output_dir or "").strip()
    if not output_dir:
        return {"ok": False, "message": "Suno output directory is missing"}
    limit = max(1, min(40, int(max_tasks_per_run or 10)))
    tasks = list_pending_tasks(db_cfg, limit)
    # #region debug-point suno-poll-tasks-loaded
    try:
        _dbg_url = os.environ.get("DEBUG_SERVER_URL") or "http://127.0.0.1:7777/event"
        _dbg_session = os.environ.get("DEBUG_SESSION_ID") or "suno-path-image-retry"
        _dbg_env = Path(__file__).resolve().parents[2] / ".dbg" / "suno-path-image-retry.env"
        if _dbg_env.exists():
            for _dbg_line in _dbg_env.read_text(encoding="utf-8", errors="ignore").splitlines():
                _dbg_line = str(_dbg_line or "").strip()
                if _dbg_line.startswith("DEBUG_SERVER_URL="):
                    _dbg_url = _dbg_line.split("=", 1)[1].strip() or _dbg_url
                elif _dbg_line.startswith("DEBUG_SESSION_ID="):
                    _dbg_session = _dbg_line.split("=", 1)[1].strip() or _dbg_session
        urllib.request.urlopen(
            urllib.request.Request(
                _dbg_url,
                data=json.dumps({"sessionId": _dbg_session, "runId": "pre-fix", "hypothesisId": "C", "location": "music_suno.poll_and_download_pending_suno:tasks_loaded", "msg": "[DEBUG] loaded pending Suno tasks", "data": {"taskCount": len(tasks or []), "fallbackOutputDir": output_dir[-120:]}}).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            ),
            timeout=2,
        ).read(1)
    except Exception:
        pass
    # #endregion
    if not tasks:
        return {"ok": True, "checked": 0, "downloaded": 0}

    batch_index_cache: dict[str, dict[str, int]] = {}
    downloaded = 0
    failed = 0
    for task in tasks:
        try:
            result = suno_api_try_get_tracks(generation_proxy, str(task.get("taskId", "")).strip())
            audio_urls = list(result.get("audioUrls") or [])
            ok_url = str(audio_urls[0] or "").strip() or None if len(audio_urls) >= 1 else None
            alt_url = str(audio_urls[1] or "").strip() or None if len(audio_urls) >= 2 else None

            ok_downloaded = bool(task.get("downloadedOk", False))
            alt_downloaded = bool(task.get("downloadedAlt", False))

            track_no = int(task.get("trackNo")) if isinstance(task.get("trackNo"), int) else None
            batch_id = str(task.get("batchId", "")).strip()
            song_uid = str(task.get("songUid", "")).strip()
            if track_no is None and batch_id and song_uid:
                index_map = batch_index_cache.get(batch_id)
                if index_map is None:
                    songs = list_songs_by_batch_id(db_cfg, batch_id)
                    index_map = {
                        str(song.get("songUid", "")).strip(): (
                            int(song.get("batchIndex")) if isinstance(song.get("batchIndex"), int) else idx + 1
                        )
                        for idx, song in enumerate(songs)
                        if str(song.get("songUid", "")).strip()
                    }
                    batch_index_cache[batch_id] = index_map
                track_no = index_map.get(song_uid)

            if ok_url:
                target_dir = str(task.get("outputDirOk", "")).strip() or output_dir
                # #region debug-point suno-poll-ok-target-dir
                try:
                    _dbg_url = os.environ.get("DEBUG_SERVER_URL") or "http://127.0.0.1:7777/event"
                    _dbg_session = os.environ.get("DEBUG_SESSION_ID") or "suno-path-image-retry"
                    _dbg_env = Path(__file__).resolve().parents[2] / ".dbg" / "suno-path-image-retry.env"
                    if _dbg_env.exists():
                        for _dbg_line in _dbg_env.read_text(encoding="utf-8", errors="ignore").splitlines():
                            _dbg_line = str(_dbg_line or "").strip()
                            if _dbg_line.startswith("DEBUG_SERVER_URL="):
                                _dbg_url = _dbg_line.split("=", 1)[1].strip() or _dbg_url
                            elif _dbg_line.startswith("DEBUG_SESSION_ID="):
                                _dbg_session = _dbg_line.split("=", 1)[1].strip() or _dbg_session
                    urllib.request.urlopen(
                        urllib.request.Request(
                            _dbg_url,
                            data=json.dumps({"sessionId": _dbg_session, "runId": "pre-fix", "hypothesisId": "C", "location": "music_suno.poll_and_download_pending_suno:ok_target_dir", "msg": "[DEBUG] resolved OK download target dir", "data": {"taskId": str(task.get("taskId", "")).strip()[:80], "batchId": batch_id[:80], "storedOutputDirOk": str(task.get("outputDirOk", "")).strip()[-120:], "storedOutputDirAlt": str(task.get("outputDirAlt", "")).strip()[-120:], "chosenTargetDir": target_dir[-120:]}}).encode("utf-8"),
                            headers={"Content-Type": "application/json"},
                            method="POST",
                        ),
                        timeout=2,
                    ).read(1)
                except Exception:
                    pass
                # #endregion
                paths = build_suno_output_paths(output_dir=target_dir, title=str(task.get("title", "")).strip(), track_no=track_no)
                if Path(paths["ok"]).exists():
                    ok_downloaded = True
                elif not ok_downloaded:
                    download_to_file(ok_url, paths["ok"])
                    ok_downloaded = True
                    downloaded += 1
            if alt_url:
                target_dir = str(task.get("outputDirAlt", "")).strip() or str(task.get("outputDirOk", "")).strip() or output_dir
                # #region debug-point suno-poll-alt-target-dir
                try:
                    _dbg_url = os.environ.get("DEBUG_SERVER_URL") or "http://127.0.0.1:7777/event"
                    _dbg_session = os.environ.get("DEBUG_SESSION_ID") or "suno-path-image-retry"
                    _dbg_env = Path(__file__).resolve().parents[2] / ".dbg" / "suno-path-image-retry.env"
                    if _dbg_env.exists():
                        for _dbg_line in _dbg_env.read_text(encoding="utf-8", errors="ignore").splitlines():
                            _dbg_line = str(_dbg_line or "").strip()
                            if _dbg_line.startswith("DEBUG_SERVER_URL="):
                                _dbg_url = _dbg_line.split("=", 1)[1].strip() or _dbg_url
                            elif _dbg_line.startswith("DEBUG_SESSION_ID="):
                                _dbg_session = _dbg_line.split("=", 1)[1].strip() or _dbg_session
                    urllib.request.urlopen(
                        urllib.request.Request(
                            _dbg_url,
                            data=json.dumps({"sessionId": _dbg_session, "runId": "pre-fix", "hypothesisId": "C", "location": "music_suno.poll_and_download_pending_suno:alt_target_dir", "msg": "[DEBUG] resolved ALT download target dir", "data": {"taskId": str(task.get("taskId", "")).strip()[:80], "batchId": batch_id[:80], "storedOutputDirOk": str(task.get("outputDirOk", "")).strip()[-120:], "storedOutputDirAlt": str(task.get("outputDirAlt", "")).strip()[-120:], "chosenTargetDir": target_dir[-120:]}}).encode("utf-8"),
                            headers={"Content-Type": "application/json"},
                            method="POST",
                        ),
                        timeout=2,
                    ).read(1)
                except Exception:
                    pass
                # #endregion
                paths = build_suno_output_paths(output_dir=target_dir, title=str(task.get("title", "")).strip(), track_no=track_no)
                if Path(paths["alt"]).exists():
                    alt_downloaded = True
                elif not alt_downloaded:
                    download_to_file(alt_url, paths["alt"])
                    alt_downloaded = True
                    downloaded += 1

            upsert_suno_task(
                db_cfg,
                {
                    "requestHash": str(task.get("requestHash", "")).strip(),
                    "songUid": str(task.get("songUid", "")).strip(),
                    "batchId": str(task.get("batchId", "")).strip(),
                    "trackNo": task.get("trackNo"),
                    "model": str(task.get("model", "")).strip(),
                    "title": str(task.get("title", "")).strip(),
                    "style": str(task.get("style", "")).strip(),
                    "instrumental": bool(task.get("instrumental", False)),
                    "taskId": str(task.get("taskId", "")).strip(),
                    "status": str(result.get("status", "")).strip(),
                    "audioUrlOk": ok_url,
                    "audioUrlAlt": alt_url,
                    "outputDirOk": str(task.get("outputDirOk", "")).strip() or None,
                    "outputDirAlt": str(task.get("outputDirAlt", "")).strip() or None,
                    "downloadedOk": ok_downloaded,
                    "downloadedAlt": alt_downloaded,
                },
            )
        except Exception:
            failed += 1
            continue

    return {"ok": True, "checked": len(tasks), "downloaded": downloaded, "failed": failed}
