/**
 * static/js/views/Dashboard.js — Home screen with due-count, streak.
 */
const { ref, onMounted } = Vue;

const DashboardView = {
  name: "Dashboard",
  setup() {
    const due     = ref(0);
    const newCards = ref(0);
    const streak  = ref(0);
    const levels  = ref([]);
    const loading = ref(true);

    async function load() {
      loading.value = true;
      try {
        const [dueRes, progressRes] = await Promise.all([
          fetch("/api/cards/due"),
          fetch("/api/progress"),
        ]);
        const dueData = await dueRes.json();
        const prog    = await progressRes.json();
        due.value     = dueData.length;
        streak.value  = prog.streak_days ?? 0;
        levels.value  = prog.level_stats ?? [];

        const newRes = await fetch("/api/cards/new");
        const newData = await newRes.json();
        newCards.value = newData.length;
      } finally {
        loading.value = false;
      }
    }

    onMounted(load);

    function levelClass(level) {
      return `pill-${level}`;
    }

    function pct(stat) {
      const total = stat.seen_count || 1;
      return Math.min(100, Math.round((stat.mastered_count / total) * 100));
    }

    return { due, newCards, streak, levels, loading, levelClass, pct };
  },

  template: `
  <div>
    <h1 class="section-title">📊 Dashboard</h1>

    <div v-if="loading" class="muted">Loading…</div>

    <template v-else>
      <!-- Stats row -->
      <div class="grid-3 mt-2">
        <div class="card" style="text-align:center">
          <div style="font-size:2.5rem;font-weight:700;color:#6c63ff">{{ due }}</div>
          <div class="muted">Cards Due Today</div>
        </div>
        <div class="card" style="text-align:center">
          <div style="font-size:2.5rem;font-weight:700;color:#4caf50">{{ newCards }}</div>
          <div class="muted">New Cards Ready</div>
        </div>
        <div class="card" style="text-align:center">
          <div style="font-size:2.5rem;font-weight:700;color:#ff9800">{{ streak }} 🔥</div>
          <div class="muted">Day Streak</div>
        </div>
      </div>

      <!-- JLPT level progress -->
      <h2 class="section-title mt-3">JLPT Level Progress</h2>
      <div style="display:flex;flex-direction:column;gap:0.75rem">
        <div v-for="stat in levels" :key="stat.level" class="card">
          <div class="flex-row">
            <span :class="['pill', 'pill-' + stat.level]">{{ stat.level }}</span>
            <span style="flex:1; padding:0 0.75rem">
              <div class="progress-bar-wrap">
                <div class="progress-bar-fill" :style="{width: pct(stat) + '%'}"></div>
              </div>
            </span>
            <span class="muted" style="font-size:0.85rem; white-space:nowrap">
              {{ stat.mastered_count }} / {{ stat.seen_count }} mastered
            </span>
          </div>
        </div>
        <div v-if="levels.length === 0" class="muted">No SRS data yet — start reviewing cards!</div>
      </div>

      <!-- Quick actions -->
      <div class="flex-row mt-3" style="gap:1rem; flex-wrap:wrap">
        <button class="btn-good" @click="$router.push('/flashcards')" style="font-size:1rem;padding:0.7rem 1.8rem">
          🃏 Start Review ({{ due }} due)
        </button>
        <button @click="$router.push('/tutor')" style="background:var(--surface2);color:var(--text);border:1px solid var(--border);font-size:1rem;padding:0.7rem 1.8rem">
          🤖 Open Tutor
        </button>
      </div>
    </template>
  </div>
  `,
};
