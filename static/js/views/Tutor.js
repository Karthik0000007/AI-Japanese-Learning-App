/**
 * static/js/views/Tutor.js — AI Tutor with SSE streaming, mode selector, and speech features.
 */
const TutorView = {
  name: "Tutor",
  setup() {
    const { ref, nextTick, onUnmounted } = Vue;

    const modes = ["TEACH", "QUIZ", "EXPLAIN", "CORRECT", "CHAT"];
    const mode = ref("CHAT");
    const messages = ref([]);
    const input = ref("");
    const transcribedText = ref(""); // Transcription result awaiting confirmation
    const busy = ref(false);
    const isRecording = ref(false);
    const isTranscribing = ref(false);
    const chatEl = ref(null);

    // Audio/Microphone state
    let mediaRecorder = null;
    let audioChunks = [];
    let audioContext = null;
    let analyser = null;
    let animationFrameId = null;

    // Audio playback queue
    const audioQueue = ref([]);
    const audioMuted = ref(false);
    const audioPlaying = ref(false);

    function closeES() {
      // SSE is handled via fetch body streaming, no EventSource needed
    }

    function scrollBottom() {
      nextTick(() => {
        if (chatEl.value) chatEl.value.scrollTop = chatEl.value.scrollHeight;
      });
    }

    function sanitize(html) {
      return typeof DOMPurify !== "undefined"
        ? DOMPurify.sanitize(html, {
            ALLOW_TAGS: ["b", "i", "ruby", "rt", "rp", "span", "br", "p", "ul", "li", "code", "strong"],
          })
        : html;
    }

    // ─── Speech-to-Text (Microphone) ─────────────────────────────────────────

    async function startRecording() {
      try {
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        audioContext = new (window.AudioContext || window.webkitAudioContext)();
        analyser = audioContext.createAnalyser();
        const source = audioContext.createMediaStreamSource(stream);
        source.connect(analyser);

        mediaRecorder = new MediaRecorder(stream);
        audioChunks = [];

        mediaRecorder.ondataavailable = (e) => audioChunks.push(e.data);
        mediaRecorder.start();

        isRecording.value = true;

        // Animate waveform (optional visual feedback)
        animateWaveform();
      } catch (err) {
        alert("Microphone access denied: " + err.message);
      }
    }

    async function stopRecording() {
      if (!mediaRecorder) return;

      isRecording.value = false;
      mediaRecorder.stop();

      mediaRecorder.onstop = async () => {
        const blob = new Blob(audioChunks, { type: "audio/wav" });
        await sendAudioToSpeechAPI(blob);
        // Stop audio stream
        mediaRecorder.stream.getTracks().forEach((t) => t.stop());
      };
    }

    async function sendAudioToSpeechAPI(audioBlob) {
      isTranscribing.value = true;
      try {
        const formData = new FormData();
        formData.append("audio", audioBlob, "audio.wav");

        const res = await fetch("/api/speech-to-text", {
          method: "POST",
          body: formData,
        });

        if (!res.ok) {
          alert("Speech-to-text failed. Make sure Whisper is available.");
          return;
        }

        const data = await res.json();
        transcribedText.value = data.text; // Show in UI for user review
      } catch (err) {
        alert("Transcription error: " + err.message);
      } finally {
        isTranscribing.value = false;
      }
    }

    function confirmTranscription() {
      if (transcribedText.value.trim()) {
        input.value = transcribedText.value;
        transcribedText.value = "";
        send();
      }
    }

    function reRecord() {
      transcribedText.value = "";
    }

    function animateWaveform() {
      if (!isRecording.value || !analyser) return;

      const dataArray = new Uint8Array(analyser.frequencyBinCount);
      analyser.getByteFrequencyData(dataArray);

      // Optional: update UI with waveform visualization
      // For now, just animate the recording state

      animationFrameId = requestAnimationFrame(animateWaveform);
    }

    // ─── TTS Audio Queue Processing ──────────────────────────────────────────

    async function processAudioQueue() {
      if (audioPlaying.value || audioQueue.value.length === 0 || audioMuted.value) return;

      audioPlaying.value = true;
      const item = audioQueue.value.shift();

      if (item.language !== "ja") {
        // Skip non-Japanese audio
        audioPlaying.value = false;
        if (audioQueue.value.length > 0) {
          processAudioQueue();
        }
        return;
      }

      try {
        // Synthesize audio for Japanese text
        const res = await fetch("/api/tts", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ text: item.text }),
        });

        if (res.ok) {
          const blob = await res.blob();
          const url = URL.createObjectURL(blob);
          const audio = new Audio(url);

          audio.onended = () => {
            URL.revokeObjectURL(url);
            audioPlaying.value = false;
            if (audioQueue.value.length > 0) {
              processAudioQueue();
            }
          };

          audio.onerror = () => {
            URL.revokeObjectURL(url);
            audioPlaying.value = false;
            if (audioQueue.value.length > 0) {
              processAudioQueue();
            }
          };

          audio.play().catch(() => {
            audioPlaying.value = false;
            if (audioQueue.value.length > 0) {
              processAudioQueue();
            }
          });
        } else {
          audioPlaying.value = false;
          if (audioQueue.value.length > 0) {
            processAudioQueue();
          }
        }
      } catch (err) {
        console.error("TTS error:", err);
        audioPlaying.value = false;
        if (audioQueue.value.length > 0) {
          processAudioQueue();
        }
      }
    }

    // ─── Tutor Chat ──────────────────────────────────────────────────────────

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
      audioQueue.value = []; // Clear audio queue for new response

      try {
        // POST to create SSE stream
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

        // Read SSE stream from response body
        const reader = res.body.getReader();
        const dec = new TextDecoder();
        let buffer = "";

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

              try {
                const item = JSON.parse(chunk);
                const token = item.token || "";
                const language = item.language || "en";
                const sentenceComplete = item.sentence_complete || false;

                // Add token to text
                messages.value[idx].text += token;
                messages.value[idx].html = sanitize(messages.value[idx].text);

                // Queue completed Japanese sentences for TTS
                if (sentenceComplete && language === "ja" && token.trim()) {
                  // Extract the completed sentence (accumulated tokens since last sentence_complete)
                  // For now, we'll queue the latest token batch
                  // In production, track sentence boundaries more precisely
                  audioQueue.value.push({
                    text: token,
                    language: language,
                    sentence_id: item.sentence_id,
                  });

                  // Start processing audio queue if not already playing
                  processAudioQueue();
                }

                scrollBottom();
              } catch (e) {
                console.error("JSON parse error:", e, "chunk:", chunk);
                messages.value[idx].text += chunk;
                messages.value[idx].html = sanitize(messages.value[idx].text);
                scrollBottom();
              }
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
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        send();
      }
    }

    onUnmounted(() => {
      closeES();
      if (animationFrameId) {
        cancelAnimationFrame(animationFrameId);
      }
      if (mediaRecorder && isRecording.value) {
        mediaRecorder.stop();
      }
    });

    return {
      modes,
      mode,
      messages,
      input,
      transcribedText,
      busy,
      isRecording,
      isTranscribing,
      chatEl,
      audioMuted,
      audioPlaying,
      send,
      onKeydown,
      startRecording,
      stopRecording,
      confirmTranscription,
      reRecord,
      processAudioQueue,
    };
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

    <!-- Transcription preview (if available) -->
    <div v-if="transcribedText" class="transcription-preview mt-1">
      <p class="muted" style="font-size:0.8rem; margin-bottom:0.3rem">Transcribed text (edit or re-record):</p>
      <div class="transcribed-text">{{ transcribedText }}</div>
      <div style="display:flex; gap:0.5rem; margin-top:0.5rem">
        <button @click="confirmTranscription" class="btn-good" style="flex:1">Send</button>
        <button @click="reRecord" class="btn-warn" style="flex:1">Re-record</button>
      </div>
    </div>

    <!-- Input & Buttons -->
    <div style="display: flex; gap: 0.5rem; margin-top: 0.75rem">
      <!-- Microphone button -->
      <button
        @click="isRecording ? stopRecording() : startRecording()"
        :disabled="busy || isTranscribing || transcribedText"
        :class="['btn-icon', { recording: isRecording }]"
        :title="isRecording ? 'Stop recording' : 'Start recording'"
      >
        {{ isRecording ? '🔴' : '🎤' }}
      </button>

      <!-- Audio controls -->
      <button
        @click="audioMuted = !audioMuted"
        :class="['btn-icon', { active: !audioMuted }]"
        title="Toggle Japanese audio"
      >
        {{ audioMuted ? '🔇' : '🔊' }}
      </button>

      <!-- Text input -->
      <input
        v-model="input"
        @keydown="onKeydown"
        placeholder="Type in English or Japanese…"
        :disabled="busy || isRecording || transcribedText"
        style="flex: 1"
      />

      <!-- Send button -->
      <button @click="send" :disabled="busy || !input.trim() || isRecording" class="btn-good">
        {{ busy ? '…' : '送' }}
      </button>
    </div>

    <p class="muted mt-1" style="font-size:0.78rem">
      Press Enter to send &nbsp;·&nbsp; Shift+Enter for newline &nbsp;·&nbsp;
      🎤 to record your voice &nbsp;·&nbsp; 🔊 to toggle Japanese audio
    </p>
  </div>
  `,
};
