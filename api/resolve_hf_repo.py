from helpers.api import ApiHandler, Request
from usr.plugins.kokoro_onnx_tts.helpers.runtime import resolve_hf_files


class ResolveHfRepo(ApiHandler):
    async def process(self, input: dict, request: Request) -> dict:
        repo = str(input.get("repo") or "").strip()
        try:
            model_file, voices_file, files = resolve_hf_files(repo)
            return {"success": True, "repo": repo, "model_file": model_file, "voices_file": voices_file, "all_files": files}
        except ValueError as exc:
            return {"success": False, "error": str(exc)}
