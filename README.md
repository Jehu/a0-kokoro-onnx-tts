# Kokoro ONNX TTS for Agent Zero

An independent Agent Zero TTS runtime plugin for local [Kokoro ONNX](https://pypi.org/project/kokoro-onnx/) speech synthesis.

It deliberately lives outside Agent Zero core and brings its ONNX-specific Python dependency through the plugin's manual **Run** setup action. It supports arbitrary public Hugging Face ONNX repositories, detects model and voices filenames automatically, caches downloaded artifacts under `usr/models/kokoro_onnx_tts/`, and optionally phonemizes configured foreign terms with a second language.

## Install and configure

1. Install the plugin from its Git repository in **Plugins**.
2. Use the plugin's **Run** action once to install `kokoro-onnx` in Agent Zero's framework environment.
3. Enable **Kokoro ONNX TTS** and open **Settings → Agent → Kokoro ONNX TTS**.
4. Enter a Hugging Face repository ID, such as `Godelaune/Kokoro-82M-ONNX-German-Martin`.
5. Click **Detect files**, set the model's voice (`martin` for the example), primary language (`de`), and save.

The first synthesis downloads and caches the selected ONNX model and voice archive.

## Mixed German/English terms

For German prose containing English technical terms, configure:

```yaml
lang: de
mixed_lang: en-us
mixed_lang_terms: API, Machine Learning, Kubernetes, Docker, React, TypeScript
```

The plugin phonemizes the normal text with `lang` and the matched terms with `mixed_lang`, then sends the composed phonemes to the ONNX runtime. This is term-based code switching; it is not automatic language detection.

## Choosing the active runtime

Agent Zero's current `ttsService` uses the first registered provider. Do not enable this plugin and the built-in **Kokoro TTS** provider at the same time until Agent Zero exposes a runtime selector. Disable the provider you do not want; browser-native TTS remains the fallback when no provider is registered.

## Dependencies and compatibility

- Runtime dependency: `kokoro-onnx>=0.5.0` (installed by `execute.py` using `uv` into Agent Zero's framework interpreter)
- System dependency: `espeak-ng`
- Python: 3.10–3.13 supported by kokoro-onnx
- Models must expose a compatible `.onnx` graph plus `.npz` or `.bin` voice archive.

## Security and storage

Only public Hugging Face repo IDs in `owner/repository` form are accepted. Download filenames reject absolute paths and `..` traversal. Model data is stored below the plugin-owned cache namespace under `usr/models/kokoro_onnx_tts/`.

## Removal

Disable or uninstall the plugin in Agent Zero's Plugins UI. Cached models are user data under `usr/models/kokoro_onnx_tts/` and can be removed separately if desired.

## License

MIT. Model licenses are controlled by their respective Hugging Face repositories.
