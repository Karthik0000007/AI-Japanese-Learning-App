/**
 * static/js/utils/health.js — Which optional services are available, and a banner
 * that explains how to turn on the ones that are not.
 *
 * Views call fetchServiceStatus() on load, disable the buttons of any service
 * that is `false`, and show <service-notice :status="..." :show="[...]">.
 */

// How to enable each optional service. Shown in the banner as plain text.
const SERVICE_HELP = {
  tutor: {
    name: "AI tutor",
    command: "docker compose --profile ai up",
    note: (s) => `Without Docker: start Ollama and run "ollama pull ${s.ollamaModel || "llama3.1:8b"}".`,
  },
  speech: {
    name: "Voice input",
    command: "pip install -r requirements-speech.txt",
    note: () => "Manual setup only; the Docker image does not include speech.",
  },
  tts: {
    name: "Japanese audio",
    command: "pip install -r requirements-speech.txt",
    note: () => "Manual setup only; the Docker image does not include text-to-speech.",
  },
};

/**
 * Returns { db, tutor, speech, tts, ollamaModel } with true/false per service.
 * If the health endpoint cannot be reached, every service is reported as false.
 */
async function fetchServiceStatus() {
  try {
    const res = await fetch("/api/health");
    if (!res.ok) throw new Error(`health returned ${res.status}`);
    const data = await res.json();
    return {
      db: data.db === "ok",
      tutor: data.ollama === "ok",
      speech: data.whisper === "ok",
      tts: data.piper === "ok",
      ollamaModel: data.ollama_model || "",
    };
  } catch {
    return { db: false, tutor: false, speech: false, tts: false, ollamaModel: "" };
  }
}

/** Banner listing the unavailable services among `show`. Renders nothing while status is unknown. */
const ServiceNotice = {
  name: "ServiceNotice",
  props: {
    status: { type: Object, default: null },  // result of fetchServiceStatus(), or null while loading
    show: { type: Array, required: true },    // e.g. ["tutor", "speech", "tts"]
  },
  computed: {
    missing() {
      if (!this.status) return [];
      return this.show
        .filter((key) => this.status[key] === false)
        .map((key) => ({ key, ...SERVICE_HELP[key], note: SERVICE_HELP[key].note(this.status) }));
    },
  },
  template: `
    <div v-if="missing.length" class="service-banner" role="status">
      <div v-for="s in missing" :key="s.key" class="service-banner-row">
        <b>{{ s.name }} is off.</b>
        To enable it run <code>{{ s.command }}</code>. <span class="muted">{{ s.note }}</span>
      </div>
    </div>
  `,
};
