"""Manual setup entry point. Run from the Agent Zero Plugins UI."""
from __future__ import annotations

import importlib.util
import subprocess
import sys


REQUIRED_MODULES = ("kokoro_onnx", "onnxruntime")


def main() -> int:
    missing = [name for name in REQUIRED_MODULES if importlib.util.find_spec(name) is None]
    if not missing:
        print("Kokoro ONNX runtime dependencies are already available.")
        print("Configure a Hugging Face repo, voice, and language in Settings > Agent > Kokoro ONNX TTS.")
        return 0

    print(f"Installing missing framework-runtime dependencies: {', '.join(missing)}")
    command = [
        "uv",
        "pip",
        "install",
        "--python",
        sys.executable,
        "kokoro-onnx>=0.5.0",
    ]
    result = subprocess.run(command, text=True)
    if result.returncode:
        print("ERROR: Dependency installation failed. Review the command output above.")
        return result.returncode

    print("Kokoro ONNX runtime dependencies installed.")
    print("Configure a Hugging Face repo, voice, and language in Settings > Agent > Kokoro ONNX TTS.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
