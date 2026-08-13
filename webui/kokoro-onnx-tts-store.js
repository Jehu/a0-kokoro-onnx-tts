import { createStore } from "/js/AlpineStore.js";
import { callJsonApi } from "/js/api.js";
import { toastFrontendError } from "/components/notifications/notification-store.js";
import { ttsService } from "/js/tts-service.js";

const PLUGIN = "kokoro_onnx_tts";
const TITLE = "Kokoro ONNX TTS";

const model = {
  initialized: false,
  statusLoaded: false,
  loading: false,
  enabled: false,
  ready: false,
  config: {},
  providerCleanup: null,

  async initRuntime() {
    if (this.initialized) return;
    this.initialized = true;
    await this.refreshStatus({ suppressError: true });
  },

  async ensureStatusLoaded() {
    if (this.statusLoaded || this.loading) return;
    await this.refreshStatus({ suppressError: true });
  },

  async refreshStatus({ suppressError = false } = {}) {
    this.loading = true;
    try {
      const status = await callJsonApi(`/plugins/${PLUGIN}/status`, {});
      this.statusLoaded = true;
      this.enabled = !!status?.enabled;
      this.ready = !!status?.ready;
      this.config = status?.config || {};

      if (this.enabled) this.registerProvider();
      else this.unregisterProvider();
    } catch (error) {
      this.unregisterProvider();
      if (!suppressError) {
        void toastFrontendError(this.errorMessage(error), TITLE);
      }
    } finally {
      this.loading = false;
    }
  },

  registerProvider() {
    if (this.providerCleanup || !this.enabled) return;

    this.providerCleanup = ttsService.registerProvider(PLUGIN, {
      synthesize: async (text) => {
        try {
          const result = await callJsonApi(`/plugins/${PLUGIN}/synthesize`, { text });
          if (!result?.success) {
            throw new Error(result?.error || "Speech synthesis failed.");
          }
          return {
            audioBase64: result.audio || "",
            mimeType: result.mime_type || "audio/wav",
          };
        } catch (error) {
          void toastFrontendError(this.errorMessage(error), TITLE);
          throw error;
        }
      },
    });
  },

  unregisterProvider() {
    if (!this.providerCleanup) return;
    this.providerCleanup();
    this.providerCleanup = null;
  },

  errorMessage(error) {
    return error instanceof Error ? error.message : String(error);
  },

  async openConfig() {
    const { store } = await import("/components/plugins/plugin-settings-store.js");
    await store.openConfig(PLUGIN);
  },

  get statusText() {
    if (!this.enabled) return "Disabled";
    if (this.loading) return "Loading";
    return this.ready ? "Ready" : "Not loaded";
  },
};

export const store = createStore("kokoroOnnxTts", model);
