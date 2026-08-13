from __future__ import annotations

import asyncio
import base64
import io
import json
import os
import re
import shutil
import tempfile
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

import soundfile as sf

from helpers import files, plugins
from helpers.print_style import PrintStyle

PLUGIN_NAME = "kokoro_onnx_tts"
DEFAULT_CONFIG = {
    "voice": "",
    "speed": 1.0,
    "lang": "en-us",
    "hf_repo": "",
    "model_file": "",
    "voices_file": "",
    "mixed_lang": "en-us",
    "mixed_lang_terms": "",
}
_REPO_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*/[A-Za-z0-9][A-Za-z0-9._-]*$")

_pipeline: Any = None
_pipeline_key: tuple[str, str] | None = None
_loading = False
_lock = asyncio.Lock()


def normalize_config(config: dict[str, Any] | None) -> dict[str, Any]:
    result = dict(DEFAULT_CONFIG)
    if not isinstance(config, dict):
        return result
    for key in ("voice", "lang", "hf_repo", "model_file", "voices_file", "mixed_lang", "mixed_lang_terms"):
        value = str(config.get(key, result[key]) or "").strip()
        if key in {"lang", "mixed_lang"}:
            value = value.lower()
        result[key] = value
    try:
        speed = float(config.get("speed", result["speed"]))
        if 0.5 <= speed <= 2.0:
            result["speed"] = speed
    except (TypeError, ValueError):
        pass
    return result


def get_config() -> dict[str, Any]:
    return normalize_config(plugins.get_plugin_config(PLUGIN_NAME) or {})


def is_enabled() -> bool:
    return plugins.determined_toggle_from_paths(True, reversed(plugins.get_plugin_roots(PLUGIN_NAME)))


def _validate_repo(repo: str) -> str:
    if not _REPO_RE.fullmatch(repo):
        raise ValueError("Hugging Face repo must have the form owner/repository.")
    return repo


def _validate_filename(filename: str) -> str:
    path = Path(filename)
    if not filename or path.is_absolute() or ".." in path.parts:
        raise ValueError("Model filenames must be non-empty relative paths without '..'.")
    return path.as_posix()


def resolve_hf_files(repo: str) -> tuple[str, str, list[str]]:
    repo = _validate_repo(repo)
    url = f"https://huggingface.co/api/models/{repo}"
    try:
        with urllib.request.urlopen(url, timeout=15) as response:
            payload = json.loads(response.read())
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            raise ValueError(f"Hugging Face repo '{repo}' was not found.") from exc
        raise ValueError(f"Hugging Face API error: {exc}") from exc
    except OSError as exc:
        raise ValueError(f"Could not query Hugging Face: {exc}") from exc

    names = [str(item.get("rfilename", "")) for item in payload.get("siblings", [])]
    onnx = [name for name in names if name.lower().endswith(".onnx")]
    voices = [name for name in names if name.lower().endswith((".npz", ".bin"))]
    if not onnx:
        raise ValueError(f"No .onnx model file found in '{repo}'.")
    if not voices:
        raise ValueError(f"No .npz or .bin voices file found in '{repo}'.")
    model = next((name for name in onnx if not any(tag in name.lower() for tag in ("int8", "quantized", "fp16", "q8"))), onnx[0])
    voice = next((name for name in voices if name.lower().endswith(".npz")), voices[0])
    return model, voice, names


def _cache_dir(repo: str) -> Path:
    return Path(files.get_abs_path("usr/models", "kokoro_onnx_tts", repo.replace("/", "_")))


def _download(repo: str, filename: str, target: Path) -> None:
    url = f"https://huggingface.co/{repo}/resolve/main/{filename}"
    target.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=target.parent, prefix=".download-", delete=False) as temp:
        temp_path = Path(temp.name)
        try:
            with urllib.request.urlopen(url, timeout=60) as response:
                shutil.copyfileobj(response, temp)
            temp_path.replace(target)
        except Exception:
            temp_path.unlink(missing_ok=True)
            raise


def _model_paths(cfg: dict[str, Any]) -> tuple[Path, Path]:
    repo = _validate_repo(cfg["hf_repo"])
    model_name, voices_name = cfg["model_file"], cfg["voices_file"]
    if not model_name or not voices_name:
        detected_model, detected_voices, _ = resolve_hf_files(repo)
        model_name = model_name or detected_model
        voices_name = voices_name or detected_voices
    model_name, voices_name = _validate_filename(model_name), _validate_filename(voices_name)
    cache_dir = _cache_dir(repo)
    model_path, voices_path = cache_dir / model_name, cache_dir / voices_name
    if not model_path.is_file():
        PrintStyle.standard(f"Downloading Kokoro ONNX model from {repo}: {model_name}")
        _download(repo, model_name, model_path)
    if not voices_path.is_file():
        PrintStyle.standard(f"Downloading Kokoro ONNX voices from {repo}: {voices_name}")
        _download(repo, voices_name, voices_path)
    return model_path, voices_path


async def preload(config: dict[str, Any] | None = None) -> None:
    global _pipeline, _pipeline_key, _loading
    cfg = normalize_config(config or get_config())
    if not cfg["hf_repo"]:
        raise ValueError("Configure a Hugging Face repo before using Kokoro ONNX TTS.")
    async with _lock:
        _loading = True
        try:
            model_path, voices_path = await asyncio.to_thread(_model_paths, cfg)
            key = (str(model_path), str(voices_path))
            if _pipeline is None or _pipeline_key != key:
                from kokoro_onnx import Kokoro
                _pipeline = Kokoro(str(model_path), str(voices_path))
                _pipeline_key = key
        finally:
            _loading = False


def _terms(raw: str) -> list[str]:
    return sorted(dict.fromkeys(term.strip() for term in re.split(r"[,\n]", raw) if term.strip()), key=len, reverse=True)


def _phonemes(text: str, cfg: dict[str, Any]) -> str:
    terms = _terms(cfg["mixed_lang_terms"])
    if not terms:
        return _pipeline.tokenizer.phonemize(text, cfg["lang"])
    pattern = re.compile(r"(?<![A-Za-z0-9_])(" + "|".join(re.escape(term) for term in terms) + r")(?![A-Za-z0-9_])", re.IGNORECASE)
    chunks: list[str] = []
    start = 0
    for match in pattern.finditer(text):
        if match.start() > start:
            chunks.append(_pipeline.tokenizer.phonemize(text[start:match.start()], cfg["lang"]))
        chunks.append(_pipeline.tokenizer.phonemize(match.group(), cfg["mixed_lang"]))
        start = match.end()
    if start < len(text):
        chunks.append(_pipeline.tokenizer.phonemize(text[start:], cfg["lang"]))
    return " ".join(chunk for chunk in chunks if chunk)


async def synthesize(text: str, config: dict[str, Any] | None = None) -> str:
    cfg = normalize_config(config or get_config())
    await preload(cfg)
    if not cfg["voice"]:
        raise ValueError("Configure a voice name for the selected model.")
    phonemes = _phonemes(text.strip(), cfg)
    samples, sample_rate = _pipeline.create(phonemes, voice=cfg["voice"], speed=cfg["speed"], is_phonemes=True)
    buffer = io.BytesIO()
    sf.write(buffer, samples, sample_rate, format="WAV")
    return base64.b64encode(buffer.getvalue()).decode("utf-8")


async def status() -> dict[str, Any]:
    return {"enabled": is_enabled(), "config": get_config(), "ready": _pipeline is not None, "loading": _loading}
