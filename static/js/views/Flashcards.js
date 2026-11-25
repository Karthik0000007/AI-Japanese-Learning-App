/**
 * static/js/views/Flashcards.js - SRS review session with card-flip animation.
 */
const FlashcardsView = {
  name: "Flashcards",
  setup() {
    const { ref, computed, onMounted, onUnmounted } = Vue;

    const queue = ref([]);
    const idx = ref(0);
    const flipped = ref(false);
    const sessionId = ref(null);
    const loading = ref(true);
    const done = ref(false);
    const stats = ref({ correct: 0, incorrect: 0 });
    const audio = ref(null);
    const ttsError = ref("");
    const services = ref(null);  // utils/health.js; null until /api/health answers
    const ttsOff = () => services.value?.tts === false;

    const card = computed(() => queue.value[idx.value] ?? null);

    async function startSession() {
      loading.value = true;
      const [dueRes, newRes, sessRes] = await Promise.all([
        fetch("/api/cards/due"),
        fetch("/api/cards/new"),
        fetch("/api/cards/sessions", { method: "POST" }),
      ]);

      const dueCards = await dueRes.json();
      const newCards = await newRes.json();
      const sess = await sessRes.json();

      sessionId.value = sess.session_id;
      queue.value = [...dueCards, ...newCards];
      done.value = queue.value.length === 0;
      loading.value = false;
    }

    async function grade(score) {
      if (!card.value) return;

      const c = card.value;
      const reviewUrl = sessionId.value
        ? `/api/cards/review?session_id=${encodeURIComponent(sessionId.value)}`
        : "/api/cards/review";

      await fetch(reviewUrl, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          card_id: c.card_id,
          grade: score,
        }),
      });

      if (score >= 3) stats.value.correct++;
      else stats.value.incorrect++;

      idx.value++;
      flipped.value = false;

      if (idx.value >= queue.value.length) {
        done.value = true;
        if (sessionId.value) {
          await fetch(`/api/cards/sessions/${sessionId.value}`, { method: "PATCH" });
        }
      }
    }

    async function playTTS() {
      if (!card.value || ttsOff()) return;

      ttsError.value = "";

      const text = resolveTtsText(card.value);
      if (!text) {
        ttsError.value = "No readable text available for this card.";
        return;
      }

      try {
        const res = await fetch("/api/tts", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ text }),
        });

        if (!res.ok) {
          ttsError.value = `TTS request failed (${res.status}).`;
          return;
        }

        const blob = await res.blob();
        if (!blob || blob.size === 0) {
          ttsError.value = "TTS returned empty audio.";
          return;
        }

        const url = URL.createObjectURL(blob);
        if (audio.value) {
          audio.value.pause();
          URL.revokeObjectURL(audio.value.src);
        }

        audio.value = new Audio(url);
        audio.value.onerror = () => {
          ttsError.value = "Audio playback failed in browser.";
        };
        audio.value.play().catch(() => {
          ttsError.value = "Browser blocked autoplay. Click Listen again.";
        });
      } catch (err) {
        ttsError.value = "TTS is unavailable right now.";
      }
    }

    function flip() {
      flipped.value = !flipped.value;
    }

    function cardFrontText(c) {
      const raw = c?.word ?? c?.character ?? c?.vocab?.word ?? c?.kanji?.character ?? "";
      const text = String(raw ?? "").trim();
      return text || "?";
    }

    function cardReading(c) {
      const raw = c?.reading ?? c?.vocab?.reading ?? "";
      return String(raw ?? "").trim();
    }

    function cardLevel(c) {
      return c?.jlpt_level ?? "";
    }

    function cardMeaning(c) {
      const raw = c?.meaning ?? c?.vocab?.meaning ?? c?.kanji?.meaning ?? "";
      if (Array.isArray(raw)) return raw.filter(Boolean).join("、");
      return String(raw ?? "").trim();
    }

    function cardOnYomi(c) {
      const raw = c?.on_yomi ?? c?.kanji?.on_yomi ?? [];
      return (Array.isArray(raw) ? raw : []).join("、");
    }

    function cardKunYomi(c) {
      const raw = c?.kun_yomi ?? c?.kanji?.kun_yomi ?? [];
      return (Array.isArray(raw) ? raw : []).join("、");
    }

    function isKanjiCard(c) {
      return c?.item_type === "kanji" || Boolean(c?.kanji);
    }

    function isVocabCard(c) {
      return c?.item_type === "vocab" || Boolean(c?.vocab);
    }

    function resolveTtsText(c) {
      // Shared helper is loaded globally from static/js/utils/tts.js.
      if (typeof getTtsTextForCard === "function") {
        const shared = String(getTtsTextForCard(c) ?? "").trim();
        if (shared) return shared;
      }

      return cardReading(c) || cardFrontText(c);
    }

    const levelClass = (level) => (level ? `pill pill-${level}` : "");

    onMounted(async () => {
      fetchServiceStatus().then((s) => { services.value = s; });
      await startSession();
    });
    onUnmounted(async () => {
      if (sessionId.value && !done.value) {
        await fetch(`/api/cards/sessions/${sessionId.value}`, { method: "PATCH" });
      }
      if (audio.value) {
        audio.value.pause();
        URL.revokeObjectURL(audio.value.src);
      }
    });

    return {
      queue,
      card,
      flipped,
      loading,
      done,
      stats,
      grade,
      flip,
      playTTS,
      levelClass,
      cardFrontText,
      cardReading,
      cardLevel,
      cardMeaning,
      cardOnYomi,
      cardKunYomi,
      isKanjiCard,
      isVocabCard,
      ttsError,
      services,
      ttsOff,
    };
  },

  template: `
  <div style="max-width:620px; margin:0 auto">
    <h1 class="section-title">🎏 Flashcard Review</h1>
    <service-notice :status="services" :show="['tts']"></service-notice>

    <div v-if="loading" class="muted">Loading cards…</div>

    <div v-else-if="done" class="card mt-2" style="text-align:center">
      <div style="font-size:3rem">🎉</div>
      <h2>Session Complete!</h2>
      <p class="muted mt-1">✅ {{ stats.correct }} correct &nbsp; ❌ {{ stats.incorrect }} incorrect</p>
      <div class="flex-row mt-2" style="justify-content:center; gap:1rem">
        <button class="btn-good" @click="$router.push('/')">Back to Dashboard</button>
      </div>
    </div>

    <template v-else-if="card">
      <p class="muted" style="text-align:right">Card {{ queue.indexOf(card)+1 }} / {{ queue.length }}</p>

      <div class="flashcard-scene mt-1" @click="flip">
        <div class="flashcard-inner" :class="{ flipped: flipped }">
          <div class="flashcard-front">
            <div class="fc-word">{{ cardFrontText(card) }}</div>
            <div class="fc-reading" v-if="isVocabCard(card)">{{ cardReading(card) || '—' }}</div>
            <div class="mt-1">
              <span :class="levelClass(cardLevel(card))">
                {{ cardLevel(card) }}
              </span>
            </div>
            <p class="muted mt-1" style="font-size:0.8rem">Tap card or press Reveal</p>
          </div>

          <div class="flashcard-back">
            <div class="fc-meaning">{{ cardMeaning(card) || 'No meaning available.' }}</div>
            <div class="fc-reading mt-1" v-if="isKanjiCard(card)">
              On: {{ cardOnYomi(card) || '—' }}
            </div>
            <div class="fc-reading" v-if="isKanjiCard(card)">
              Kun: {{ cardKunYomi(card) || '—' }}
            </div>
          </div>
        </div>
      </div>

      <div style="text-align:center; margin-top:0.5rem; display:flex; gap:0.5rem; justify-content:center; flex-wrap:wrap">
        <button @click.stop="flip" style="background:var(--surface2);color:var(--text);border:1px solid var(--border)">
          {{ flipped ? 'Hide' : 'Reveal' }}
        </button>
        <button @click.stop="playTTS" :disabled="ttsOff()" :title="ttsOff() ? 'Japanese audio is off (see the note above)' : 'Listen'"
                style="background:var(--surface2);color:var(--text);border:1px solid var(--border)">
          🔊 Listen
        </button>
      </div>
      <p v-if="ttsError" class="muted mt-1" style="text-align:center; color: var(--warn)">{{ ttsError }}</p>

      <div class="grade-buttons mt-2" v-if="flipped">
        <button class="btn-again" @click="grade(0)">Again<br><small>forgot</small></button>
        <button class="btn-hard" @click="grade(2)">Hard<br><small>struggled</small></button>
        <button class="btn-good" @click="grade(3)">Good<br><small>recalled</small></button>
        <button class="btn-easy" @click="grade(5)">Easy<br><small>instant recall</small></button>
      </div>
      <p class="muted mt-1" style="text-align:center; font-size:0.8rem" v-else>
        Grade buttons will appear after you flip the card.
      </p>
    </template>
  </div>
  `,
};
