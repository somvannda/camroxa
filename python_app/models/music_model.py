from __future__ import annotations

from copy import deepcopy
from datetime import datetime
import uuid


def now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def create_id(prefix: str) -> str:
    base = str(prefix or "item").strip().lower() or "item"
    return f"{base}-{uuid.uuid4().hex[:10]}"


DEFAULT_SETTINGS: dict = {
    "language": "English",
    "creativity": 55,
    "sort": 1,
    "template": "Default",
    "activeProfileId": None,
    "activeProfileOkId": None,
    "activeProfileAltId": None,
    "channelOkProfileIds": [],
    "channelAltProfileIds": [],
    "activeDescriptionIds": [],
    "activeStructureIds": [],
    "matchDescriptionStructure": False,
    "showLatest": True,
    "shuffle": False,
    "shuffleDescription": False,
    "shuffleStructure": False,
    "useAllDescriptions": False,
    "useAllStructures": False,
    "enabledDescriptionIds": [],
    "enabledStructureIds": [],
    "uniqueOpening": False,
    "strictLevel": 3,
    "uniquenessHistoryWindow": 100,
    "cycleStructures": False,
    "mergeChunkSize": 7,
    "songDraftProvider": "deepseek",
    "titleAlbumProvider": "deepseek",
    "lyricsProvider": "deepseek",
    "titleAlbumTimeoutSec": 30,
    "titleAlbumMaxAttempts": 6,
    "songDraftTimeoutSec": 30,
    "songDraftMaxAttempts": 8,
    "poolPickMaxAttempts": 5,
    "batchMaxExtraAttempts": 0,
    "openaiApiKey": "",
    "slaiSongModel": "gpt-5.5",
    "slaiImgModel": "cgpt-web/gpt-5.5-pro",
    "falImgModel": "flux-dev-i2i",
    "imageBackgroundProvider": "slai",
    "imageThumbnailProvider": "slai",
    "youtubeClientId": "",
    "youtubeClientSecret": "",
    "ffmpegPath": "",
    "pythonPath": "",
    "downloadsDir": "D:\\MusicGenerator\\downloads",
    "mergedDir": "D:\\MusicGenerator\\merged",
    "defaultSongCount": 1,
    "imageOutputDir": "D:\\MusicGenerator\\images",
    "imageResolution": "1920x1080",
    "outputResolution": "1920x1080",
    "styleStrength": 60,
    "backgroundSourceMode": "samples",
    "thumbnailOverlayMode": "ai",
    "backgroundTemplateCycleIndex": 0,
    "imageBackgroundSamplesDir": "",
    "imageThumbnailSamplesDir": "",
    "imageSamplesDir": "",
    "imageBgRandom": False,
    "imageThumbRandom": False,
    "videoMergeDirectories": [],
    "videoExport": {
        "resolution": "1920x1080",
        "fps": 30,
        "codec": "h264",
        "preset": "fast",
        "crf": 20,
        "audioBitrateKbps": 192,
    },
    "videoRenderOutputDir": "D:\\MusicGenerator\\videos",
    "videoExportSpeedMode": "balanced",
    "videoRenderTemplatePath": "",
    "videoRenderBackgroundPath": "",
    "perfMusicWorkers": 1,
    "perfImageWorkers": 4,
    "perfMergeWorkers": 1,
    "perfYouTubeWorkers": 1,
    "youtubeUploadChunkSizeMb": 256,
    "autoGenSongs": True,
    "autoGenImage": True,
    "autoGSuno": False,
    "autoVideoAfterSuno": False,
    "autoMergeAfterVideo": False,
    "autoReelAfterVideo": False,
    "autoUploadYouTube": False,
    "lyricsPolishStrength": 60,
    "sunoTimeoutMs": 90000,
    "sunoRetryCount": 3,
    "sunoDefaultVersion": "v5.5",
    "sunoMergeEnabled": False,
    "sunoMergeGroupSize": 5,
    "sunoApiBaseUrl": "https://api.sunoapi.org",
    "sunoCreditsReserve": 10,
    "sunoCreditsCostMusic": 5,
    "sunoCreditsCostLyrics": 1,
    "sunoOutputDir": "D:\\MusicGenerator\\downloads\\suno",
    "sunoCallbackUrl": "https://api.example.com/callback",
    "platformApiBaseUrl": "http://localhost:8000/api/v1",
    "dbHost": "localhost",
    "dbPort": 5432,
    "dbUser": "postgres",
    "dbPassword": "postgres",
    "dbName": "MG",
}

# Keys removed from the desktop app (now managed by Platform API).
# When loading old config files containing these keys, they are silently discarded.
REMOVED_API_KEY_FIELDS: set[str] = {
    "sunoApiKey",
    "deepseekApiKey",
    "slaiLlmApiKey",
    "slaiSongApiKey",
    "falImgApiKey",
    "slaiImgApiKey",
}


def default_music_app_data() -> dict:
    updated_at = now_iso()
    return {
        "descriptions": [
            {
                "id": "desc-01",
                "name": "01",
                "content": (
                    "High-energy dance track with strong hook, big chorus, emotional lift, and a modern "
                    "electronic arrangement. Keep the writing catchy, visual, and performance-ready."
                ),
                "updatedAt": updated_at,
            }
        ],
        "structures": [
            {
                "id": "struct-01",
                "name": "Festival",
                "content": (
                    "[Intro]\n[Verse]\n[Pre-Chorus]\n[Chorus]\n[Verse]\n[Pre-Chorus]\n"
                    "[Chorus]\n[Bridge]\n[Final Chorus]\n[Outro]"
                ),
                "updatedAt": updated_at,
            }
        ],
        "songs": [],
        "songDrafts": [{"id": "draft-01", "title": "", "album": ""}],
        "profiles": [],
        "carModels": [],
        "imageSamples": [],
        "promptTemplates": [],
        "textStyles": [],
        "history": [],
        "settings": deepcopy(DEFAULT_SETTINGS),
    }


def normalize_saved_text(item: dict, fallback_prefix: str) -> dict:
    row = item if isinstance(item, dict) else {}
    return {
        "id": str(row.get("id", "")).strip() or create_id(fallback_prefix),
        "name": str(row.get("name", "")).strip() or "Untitled",
        "content": str(row.get("content", "") or row.get("text", "")),
        "matchKey": str(row.get("matchKey", "")).strip(),
        "updatedAt": str(row.get("updatedAt", "")).strip() or now_iso(),
    }


def normalize_song(item: dict) -> dict:
    row = item if isinstance(item, dict) else {}
    return {
        "id": str(row.get("id", "")).strip() or create_id("song"),
        "title": str(row.get("title", "")).strip(),
        "album": str(row.get("album", "")).strip(),
        "lyricsRaw": str(row.get("lyricsRaw", "")).strip(),
        "lyricsPolished": str(row.get("lyricsPolished", "")).strip(),
        "batchIndex": row.get("batchIndex"),
        "songDescriptionTitle": str(row.get("songDescriptionTitle", "")).strip(),
        "songStructureTitle": str(row.get("songStructureTitle", "")).strip(),
        "songDescription": str(row.get("songDescription", "")).strip(),
        "songStructure": str(row.get("songStructure", "")).strip(),
        "profileOkId": str(row.get("profileOkId", "")).strip(),
        "profileAltId": str(row.get("profileAltId", "")).strip(),
        "profileOkName": str(row.get("profileOkName", "")).strip(),
        "profileAltName": str(row.get("profileAltName", "")).strip(),
        "language": str(row.get("language", "English")).strip() or "English",
        "creativity": int(row.get("creativity", 55) or 55),
        "batchId": str(row.get("batchId", "")).strip(),
        "createdAt": str(row.get("createdAt", "")).strip() or now_iso(),
    }


def normalize_song_draft(item: dict) -> dict:
    row = item if isinstance(item, dict) else {}
    return {
        "id": str(row.get("id", "")).strip() or create_id("draft"),
        "title": str(row.get("title", "")).strip(),
        "album": str(row.get("album", "")).strip(),
    }


def normalize_profile(item: dict) -> dict:
    row = item if isinstance(item, dict) else {}
    ts = str(row.get("updatedAt", "")).strip() or now_iso()
    raw_image_cfg = row.get("imageConfig")
    image_cfg_in = raw_image_cfg if isinstance(raw_image_cfg, dict) else {}

    def _opt_bool(key: str) -> bool | None:
        if key not in image_cfg_in:
            return None
        value = image_cfg_in.get(key)
        if value is None:
            return None
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            return bool(value)
        text = str(value).strip().lower()
        if text in {"true", "1", "yes", "y", "on"}:
            return True
        if text in {"false", "0", "no", "n", "off"}:
            return False
        return bool(text)

    bg_samples_raw = image_cfg_in.get("backgroundSamples")
    thumb_samples_raw = image_cfg_in.get("thumbnailSamples")
    image_cfg = {
        "mode": str(image_cfg_in.get("mode", "bg_thumb")).strip() or "bg_thumb",
        "basePrompt": str(image_cfg_in.get("basePrompt", "")).strip(),
        "backgroundPrompt": str(image_cfg_in.get("backgroundPrompt", "")).strip(),
        "thumbnailPrompt": str(image_cfg_in.get("thumbnailPrompt", "")).strip(),
        "thumbnailIncludeTrackTitles": _opt_bool("thumbnailIncludeTrackTitles"),
        "backgroundSamplesDir": str(image_cfg_in.get("backgroundSamplesDir", "")).strip(),
        "thumbnailSamplesDir": str(image_cfg_in.get("thumbnailSamplesDir", "")).strip(),
        "backgroundRandom": _opt_bool("backgroundRandom"),
        "thumbnailRandom": _opt_bool("thumbnailRandom"),
        "backgroundSamples": [str(x).strip() for x in bg_samples_raw if str(x).strip()] if isinstance(bg_samples_raw, list) else [],
        "thumbnailSamples": [str(x).strip() for x in thumb_samples_raw if str(x).strip()] if isinstance(thumb_samples_raw, list) else [],
    }
    return {
        "id": str(row.get("id", "")).strip() or create_id("profile"),
        "name": str(row.get("name", "")).strip() or "Unnamed Profile",
        "folderName": str(row.get("folderName", "")).strip(),
        "runPrefix": str(row.get("runPrefix", "")).strip(),
        "logoPath": str(row.get("logoPath", "")).strip(),
        "videoTemplateId": str(row.get("videoTemplateId", "")).strip(),
        "reelTemplateId": str(row.get("reelTemplateId", "")).strip(),
        "outputResolution": str(row.get("outputResolution", "")).strip(),
        "imageConfig": image_cfg,
        "youtubeVisibilityMode": str(row.get("youtubeVisibilityMode", "")).strip() or "unlisted",
        "youtubePublishAt": str(row.get("youtubePublishAt", "")).strip(),
        "youtubeCategoryId": str(row.get("youtubeCategoryId", "")).strip(),
        "youtubePlaylistId": str(row.get("youtubePlaylistId", "")).strip(),
        "youtubeTags": str(row.get("youtubeTags", "")).strip(),
        "youtubeTitleTemplate": str(row.get("youtubeTitleTemplate", "")).strip(),
        "youtubeDescriptionTemplate": str(row.get("youtubeDescriptionTemplate", "")).strip(),
        "youtubeMadeForKids": bool(row.get("youtubeMadeForKids", False)),
        "youtubeContainsSyntheticMedia": bool(row.get("youtubeContainsSyntheticMedia", False)),
        "youtubeOauthAppId": str(row.get("youtubeOauthAppId", "")).strip(),
        "createdAt": str(row.get("createdAt", "")).strip() or ts,
        "updatedAt": ts,
    }


def normalize_music_app_data(raw: dict | None) -> dict:
    base = default_music_app_data()
    src = raw if isinstance(raw, dict) else {}
    settings = src.get("settings") if isinstance(src.get("settings"), dict) else {}
    out = deepcopy(base)
    merged = {**deepcopy(DEFAULT_SETTINGS), **settings}
    # Silently discard removed API key fields from old config files
    for key in REMOVED_API_KEY_FIELDS:
        merged.pop(key, None)
    if not str(merged.get("titleAlbumProvider", "") or "").strip():
        merged["titleAlbumProvider"] = str(merged.get("songDraftProvider", "deepseek")).strip() or "deepseek"
    if not str(merged.get("lyricsProvider", "") or "").strip():
        merged["lyricsProvider"] = str(merged.get("titleAlbumProvider", "deepseek")).strip() or "deepseek"
    out["settings"] = merged
    out["descriptions"] = [normalize_saved_text(x, "desc") for x in (src.get("descriptions") or []) if isinstance(x, dict)] or out["descriptions"]
    out["structures"] = [normalize_saved_text(x, "struct") for x in (src.get("structures") or []) if isinstance(x, dict)] or out["structures"]
    out["songs"] = [normalize_song(x) for x in (src.get("songs") or []) if isinstance(x, dict)]
    out["songDrafts"] = [normalize_song_draft(x) for x in (src.get("songDrafts") or []) if isinstance(x, dict)] or out["songDrafts"]
    out["profiles"] = [normalize_profile(x) for x in (src.get("profiles") or []) if isinstance(x, dict)]
    out["carModels"] = list(src.get("carModels") or [])
    out["imageSamples"] = list(src.get("imageSamples") or [])
    out["promptTemplates"] = list(src.get("promptTemplates") or [])
    out["textStyles"] = list(src.get("textStyles") or [])
    out["history"] = list(src.get("history") or [])
    return out


def next_saved_text_name(items: list[dict]) -> str:
    nums: list[int] = []
    for item in items:
        name = str((item or {}).get("name", "")).strip()
        try:
            nums.append(int(name))
        except Exception:
            continue
    next_num = (max(nums) + 1) if nums else 1
    return str(next_num).zfill(2)
