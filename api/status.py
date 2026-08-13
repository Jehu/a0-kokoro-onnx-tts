import importlib.metadata

from helpers.api import ApiHandler, Request
from usr.plugins.kokoro_onnx_tts.helpers import runtime


class Status(ApiHandler):
    async def process(self, input: dict, request: Request) -> dict:
        state = await runtime.status()
        try:
            version, error = importlib.metadata.version("kokoro-onnx"), ""
        except Exception as exc:
            version, error = "", str(exc)
        return {"plugin": "kokoro_onnx_tts", **state, "package": {"version": version, "error": error}}
