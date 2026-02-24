/**
 * static/js/views/Flashcards.js — SRS review session with card-flip animation.
 */
const FlashcardsView = {
  name: "Flashcards",
  setup() {
    const { ref, computed, onMounted, onUnmounted } = Vue;

    const queue     = ref([]);   // due + new cards
    const idx       = ref(0);
    const flipped   = ref(false);
    const sessionId = ref(null);
    const loading   = ref(true);
    const done      = ref(false);
    const stats     = ref({ correct: 0, incorrect: 0 });
    const audio     = ref(null); // Audio object for TTS

    const card = computed(() => queue.value[idx.value] ?? null);

    async function startSession() {
      loading.value = true;
      const [dueRes, newRes, sessRes] = await Promise.all([
        fetch("/api/cards/due"),
        fetch("/api/cards/new"),
        fetch("/api/cards/sessions", { method: "POST" }),
      ]);
      const dueCards  = await dueRes.json();
      const newCards  = await newRes.json();
      const sess      = await sessRes.json();
      sessionId.value = sess.id;
      queue.value     = [...dueCards, ...newCards];
      if (queue.value.length === 0) done.value = true;
      loading.value = false;
    }

    async function grade(score) {
      if (!card.value) return;
      const c = card.value;
      await fetch("/api/cards/review", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          item_type:  c.item_type,
          item_id:    c.item_id,
          score,
          session_id: sessionId.value,
        }),
      });
      if (score >= 3) stats.value.correct++;
      else            stats.value.incorrect++;
      idx.value++;
      flipped.value = false;
      if (idx.value >= queue.value.length) {
        done.value = true;
        await fetch(`/api/cards/sessions/${sessionId.value}`, { method: "PATCH" });
      }
    }

    async function playTTS() {
      if (!card.value) return;
      const word = card.value.vocab?.word ?? card.value.kanji?.character ?? "";
      if (!word) return;
      try {
        const res = await fetch("/api/tts", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ text: word }),
        });
        if (!res.ok) return;
        const blob = await res.blob();
        const url  = URL.createObjectURL(blob);
        if (audio.value) { audio.value.pause(); URL.revokeObjectURL(audio.value.src); }
        audio.value = new Audio(url);
        audio.value.play();
      } catch { /* TTS unavailable — silent fail */ }
    }

    function flip() { flipped.value = !flipped.value; }

    const levelClass = (level) => level ? `pill pill-${level}` : "";

    onMounted(startSession);
    onUnmounted(async () => {
      if (sessionId.value && !done.value) {
        await fetch(`/api/cards/sessions/${sessionId.value}`, { method: "PATCH" });
      }
    });

    return { queue, card, flipped, loading, done, stats, grade, flip, playTTS, levelClass };
  },

  template: `
  <div style="max-width:620px; margin:0 auto">
    <h1 class="section-title">🃏 Flashcard Review</h1>

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
      <!-- Progress indicator -->
      <p class="muted" style="text-align:right">Card {{ queue.indexOf(card)+1 }} / {{ queue.length }}</p>

      <!-- Card -->
      <div class="flashcard-scene mt-1" @click="flip">
        <div :class="['flashcard-inner', { flipped }]">
          <!-- Front -->
          <div class="flashcard-front">
            <div class="fc-word">{{ card.vocab?.word ?? card.kanji?.character ?? '?' }}</div>
            <div class="fc-reading" v-if="card.vocab">{{ card.vocab.reading }}</div>
            <div class="mt-1">
              <span :class="levelClass(card.vocab?.jlpt_level ?? card.kanji?.jlpt_level)">
                {{ card.vocab?.jlpt_level ?? card.kanji?.jlpt_level ?? '' }}
              </span>
            </div>
            <p class="muted mt-1" style="font-size:0.8rem">Tap to reveal answer</p>
          </div>
          <!-- Back -->
          <div class="flashcard-back">
            <div class="fc-meaning">{{ card.vocab?.meaning ?? (card.kanji?.meaning ?? []).join('、') }}</div>
            <div class="fc-reading mt-1" v-if="card.kanji">
              On: {{ (card.kanji.on_yomi ?? []).join('、') }}
            </div>
            <div class="fc-reading" v-if="card.kanji">
              Kun: {{ (card.kanji.kun_yomi ?? []).join('、') }}
            </div>
          </div>
        </div>
      </div>

      <!-- TTS button -->
      <div style="text-align:center; margin-top:0.5rem">
        <button @click.stop="playTTS" style="background:var(--surface2);color:var(--text);border:1px solid var(--border)">
          🔊 Listen
        </button>
      </div>

      <!-- Grade buttons (only when flipped) -->
      <div class="grade-buttons mt-2" v-if="flipped">
        <button class="btn-again" @click="grade(0)">Again<br><small>forgot</small></button>
        <button class="btn-hard"  @click="grade(2)">Hard<br><small>struggled</small></button>
        <button class="btn-good"  @click="grade(3)">Good<br><small>recalled</small></button>
        <button class="btn-easy"  @click="grade(5)">Easy<br><small>instant recall</small></button>
      </div>
      <p class="muted mt-1" style="text-align:center; font-size:0.8rem" v-else>
        Grade buttons will appear after you flip the card.
      </p>
    </template>
  </div>
  `,
};
