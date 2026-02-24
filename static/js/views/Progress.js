/**
 * static/js/views/Progress.js — streak calendar, accuracy, 7-day forecast.
 */
const ProgressView = {
  name: "Progress",
  setup() {
    const { ref, onMounted } = Vue;

    const streak    = ref(0);
    const accuracy  = ref(0);
    const levels    = ref([]);
    const forecast  = ref([]);
    const loading   = ref(true);

    async function load() {
      loading.value = true;
      const res  = await fetch("/api/progress");
      const data = await res.json();
      streak.value   = data.streak_days    ?? 0;
      accuracy.value = data.accuracy_pct   ?? 0;
      levels.value   = data.level_stats    ?? [];
      forecast.value = data.weekly_forecast ?? [];
      loading.value  = false;
    }

    onMounted(load);

    function accColor(pct) {
      if (pct >= 80) return "var(--ok)";
      if (pct >= 50) return "var(--warn)";
      return "var(--err)";
    }

    function maxForecast() {
      return Math.max(...forecast.value.map(d => d.due_count), 1);
    }

    return { streak, accuracy, levels, forecast, loading, accColor, maxForecast };
  },

  template: `
  <div>
    <h1 class="section-title">📈 Progress</h1>

    <div v-if="loading" class="muted">Loading…</div>
    <template v-else>

      <!-- Top stats -->
      <div class="grid-3 mt-2">
        <div class="card" style="text-align:center">
          <div style="font-size:2.5rem;font-weight:700;color:#ff9800">{{ streak }} 🔥</div>
          <div class="muted">Day Streak</div>
        </div>
        <div class="card" style="text-align:center">
          <div :style="{fontSize:'2.5rem',fontWeight:700,color:accColor(accuracy)}">{{ accuracy }}%</div>
          <div class="muted">All-time Accuracy</div>
        </div>
        <div class="card" style="text-align:center">
          <div style="font-size:2.5rem;font-weight:700;color:var(--accent)">{{ levels.reduce((s,l)=>s+l.mastered_count,0) }}</div>
          <div class="muted">Cards Mastered</div>
        </div>
      </div>

      <!-- JLPT per-level breakdown -->
      <h2 class="section-title mt-3">Level Breakdown</h2>
      <div style="display:flex; flex-direction:column; gap:0.6rem">
        <div v-for="stat in levels" :key="stat.level" class="card">
          <div class="flex-row">
            <span :class="['pill','pill-'+stat.level]" style="width:34px;text-align:center">{{ stat.level }}</span>
            <div style="flex:1; padding: 0 0.75rem">
              <div class="progress-bar-wrap">
                <div class="progress-bar-fill" :style="{width: stat.seen_count ? Math.round(stat.mastered_count/stat.seen_count*100)+'%' : '0%'}"></div>
              </div>
            </div>
            <div style="font-size:0.82rem; color:var(--muted); white-space:nowrap">
              {{ stat.mastered_count }} / {{ stat.total_count }} &nbsp;({{ stat.seen_count }} seen)
            </div>
          </div>
        </div>
        <div v-if="levels.length === 0" class="muted">No review data yet.</div>
      </div>

      <!-- 7-day forecast -->
      <h2 class="section-title mt-3">7-Day Review Forecast</h2>
      <div class="card" style="padding:1.5rem">
        <div style="display:flex; align-items:flex-end; gap:0.5rem; height:100px">
          <div v-for="day in forecast" :key="day.date"
               style="flex:1; display:flex; flex-direction:column; align-items:center; gap:0.3rem">
            <span class="muted" style="font-size:0.7rem">{{ day.due_count }}</span>
            <div :style="{
              height: (day.due_count / maxForecast() * 80) + 'px',
              background: 'var(--accent)',
              width: '100%',
              borderRadius: '4px 4px 0 0',
              minHeight: day.due_count ? '4px' : '1px',
              opacity: 0.8
            }"></div>
            <span class="muted" style="font-size:0.7rem">{{ day.date.slice(5) }}</span>
          </div>
        </div>
      </div>
      <p class="muted mt-1" style="font-size:0.8rem">Number of SRS cards due per day for the next 7 days.</p>

    </template>
  </div>
  `,
};
