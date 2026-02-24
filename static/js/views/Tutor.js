/**
 * static/js/views/Tutor.js — AI Tutor with SSE streaming and mode selector.
 */
const TutorView = {
  name: "Tutor",
  setup() {
    const { ref, nextTick, onUnmounted } = Vue;

    const modes   = ["TEACH", "QUIZ", "EXPLAIN", "CORRECT", "CHAT"];
    const mode    = ref("CHAT");
    const messages = ref([]);
    const input   = ref("");
    const busy    = ref(false);
    const chatEl  = ref(null);
    let   es      = null;  // EventSource

    function closeES() {
      if (es) { es.close(); es = null; }
    }

    function scrollBottom() {
      nextTick(() => {
        if (chatEl.value) chatEl.value.scrollTop = chatEl.value.scrollHeight;
      });
    }

    function sanitize(html) {
      return typeof DOMPurify !== "undefined"
        ? DOMPurify.sanitize(html, { ALLOW_TAGS: ["b","i","ruby","rt","rp","span","br","p","ul","li","code","strong"] })
        : html;
    }

    async function send() {
      const text = input.value.trim();
      if (!text || busy.value) return;

      input.value = "";
      messages.value.push({ role: "user", text });
      scrollBottom();

      // Add empty tutor bubble to stream into
      const idx = messages.value.length;
      messages.value.push({ role: "tutor", text: "", html: "" });
      scrollBottom();

      busy.value = true;
      closeES();

      try {
        // POST first to create the SSE stream
        const res = await fetch("/api/tutor/chat", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ message: text, mode: mode.value }),
        });

        if (!res.ok) {
          messages.value[idx].text = "⚠️ Tutor unavailable. Make sure Ollama is running.";
          busy.value = false;
          return;
        }

        // Read SSE stream from the response body directly
        const reader = res.body.getReader();
        const dec    = new TextDecoder();
        let   buffer = "";

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;
          buffer += dec.decode(value, { stream: true });
          const lines = buffer.split("\n");
          buffer = lines.pop();
          for (const line of lines) {
            if (line.startsWith("data: ")) {
              const chunk = line.slice(6);
              if (chunk === "[DONE]") continue;
              messages.value[idx].text += chunk;
              messages.value[idx].html  = sanitize(messages.value[idx].text);
              scrollBottom();
            }
          }
        }
      } catch (e) {
        messages.value[idx].text = "⚠️ Stream error: " + e.message;
      } finally {
        busy.value = false;
        scrollBottom();
      }
    }

    function onKeydown(e) {
      if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(); }
    }

    onUnmounted(closeES);

    return { modes, mode, messages, input, busy, chatEl, send, onKeydown };
  },

  template: `
  <div style="max-width:760px; margin:0 auto">
    <h1 class="section-title">🤖 AI Tutor</h1>

    <!-- Mode tabs -->
    <div class="mode-tabs">
      <button v-for="m in modes" :key="m"
              :class="['mode-tab', {active: mode === m}]"
              @click="mode = m">{{ m }}</button>
    </div>
    <p class="muted" style="font-size:0.8rem; margin-bottom:0.75rem">
      <b>TEACH</b> — explain concepts &nbsp;|&nbsp;
      <b>QUIZ</b>  — test yourself &nbsp;|&nbsp;
      <b>EXPLAIN</b> — grammar deep-dive &nbsp;|&nbsp;
      <b>CORRECT</b> — submit your Japanese for correction &nbsp;|&nbsp;
      <b>CHAT</b> — free conversation
    </p>

    <!-- Chat window -->
    <div class="chat-window" ref="chatEl">
      <div v-if="messages.length === 0" class="muted" style="align-self:center; margin:auto">
        Start chatting with your AI Japanese tutor!
      </div>
      <div v-for="(msg, i) in messages" :key="i"
           :class="['chat-bubble', msg.role === 'user' ? 'user' : 'tutor']">
        <template v-if="msg.role === 'tutor' && msg.html">
          <span v-html="msg.html"></span>
        </template>
        <template v-else>{{ msg.text }}</template>
        <span v-if="msg.role === 'tutor' && !msg.text && busy" style="opacity:0.6">▋</span>
      </div>
    </div>

    <!-- Input -->
    <div class="chat-input-row mt-1">
      <input v-model="input" @keydown="onKeydown" placeholder="Type in English or Japanese…" :disabled="busy" />
      <button @click="send" :disabled="busy || !input.trim()" class="btn-good">
        {{ busy ? '…' : '送' }}
      </button>
    </div>
    <p class="muted mt-1" style="font-size:0.78rem">
      Press Enter to send &nbsp;·&nbsp; Shift+Enter for newline &nbsp;·&nbsp;
      The tutor will <em>not</em> translate for you — it teaches.
    </p>
  </div>
  `,
};
