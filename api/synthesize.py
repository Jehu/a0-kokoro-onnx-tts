from helpers.api import ApiHandler, Request, Response
from usr.plugins.kokoro_onnx_tts.helpers import runtime


class Synthesize(ApiHandler):
    async def process(self, input: dict, request: Request) -> dict | Response:
        if not runtime.is_enabled():
            return Response(status=409, response="Kokoro ONNX TTS plugin is disabled")
        text = str(input.get("text") or "").strip()
        if not text:
            return Response(status=400, response="Missing text")
        try:
            return {"success": True, "audio": await runtime.synthesize(text), "mime_type": "audio/wav"}
        except Exception as exc:
            return {"success": False, "error": str(exc)}
