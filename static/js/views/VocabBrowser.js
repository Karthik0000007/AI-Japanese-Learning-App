/**
 * static/js/views/VocabBrowser.js — Browsable, searchable vocabulary list.
 */
const VocabBrowserView = {
  name: "VocabBrowser",
  setup() {
    const { ref, watch, onMounted } = Vue;

    const items    = ref([]);
    const total    = ref(0);
    const page     = ref(1);
    const pageSize = 40;
    const search   = ref("");
    const level    = ref("");
    const loading  = ref(false);
    let debounceTimer = null;

    async function load() {
      loading.value = true;
      const params = new URLSearchParams({
        page:  page.value,
        limit: pageSize,
      });
      if (search.value) params.set("search", search.value);
      if (level.value)  params.set("level",  level.value);
      const res  = await fetch(`/api/vocab?${params}`);
      const data = await res.json();
      items.value = data.items ?? [];
      total.value = data.total ?? 0;
      loading.value = false;
    }

    function onSearchInput() {
      clearTimeout(debounceTimer);
      debounceTimer = setTimeout(() => { page.value = 1; load(); }, 350);
    }

    watch(level, () => { page.value = 1; load(); });

    onMounted(load);

    const totalPages = () => Math.ceil(total.value / pageSize);
    const prev = () => { if (page.value > 1) { page.value--; load(); } };
    const next = () => { if (page.value < totalPages()) { page.value++; load(); } };

    return { items, total, page, search, level, loading, onSearchInput, prev, next, totalPages };
  },

  template: `
  <div>
    <h1 class="section-title">📖 Vocabulary Browser</h1>

    <!-- Filters -->
    <div class="flex-row" style="flex-wrap:wrap; gap:0.75rem; margin-bottom:1rem">
      <input v-model="search" @input="onSearchInput" placeholder="Search word / meaning…" style="flex:1; min-width:180px" />
      <select v-model="level" style="width:110px">
        <option value="">All levels</option>
        <option>N5</option><option>N4</option><option>N3</option><option>N2</option><option>N1</option>
      </select>
      <span class="muted">{{ total }} entries</span>
    </div>

    <div v-if="loading" class="muted">Loading…</div>

    <table v-else style="width:100%; border-collapse:collapse">
      <thead>
        <tr style="border-bottom:1px solid var(--border); color:var(--muted); font-size:0.85rem; text-align:left">
          <th style="padding:0.5rem 0.4rem">Word</th>
          <th style="padding:0.5rem 0.4rem">Reading</th>
          <th style="padding:0.5rem 0.4rem">Meaning</th>
          <th style="padding:0.5rem 0.4rem">POS</th>
          <th style="padding:0.5rem 0.4rem">Level</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="v in items" :key="v.id"
            style="border-bottom:1px solid var(--border); transition:background 0.1s"
            @mouseenter="$event.currentTarget.style.background='var(--surface2)'"
            @mouseleave="$event.currentTarget.style.background=''">
          <td style="padding:0.55rem 0.4rem; font-family:var(--font-jp); font-size:1.15rem">{{ v.word }}</td>
          <td style="padding:0.55rem 0.4rem; color:var(--muted)">{{ v.reading }}</td>
          <td style="padding:0.55rem 0.4rem; font-size:0.9rem">{{ v.meaning }}</td>
          <td style="padding:0.55rem 0.4rem; font-size:0.8rem; color:var(--muted)">{{ v.part_of_speech }}</td>
          <td style="padding:0.55rem 0.4rem">
            <span v-if="v.jlpt_level" :class="['pill', 'pill-' + v.jlpt_level]">{{ v.jlpt_level }}</span>
          </td>
        </tr>
      </tbody>
    </table>

    <div v-if="items.length === 0 && !loading" class="muted mt-2" style="text-align:center">
      No vocabulary found. Run <code>python tools/setup.py</code> to seed the database.
    </div>

    <!-- Pagination -->
    <div class="pagination mt-2">
      <button :disabled="page <= 1" @click="prev">‹ Prev</button>
      <span class="muted">Page {{ page }} / {{ totalPages() }}</span>
      <button :disabled="page >= totalPages()" @click="next">Next ›</button>
    </div>
  </div>
  `,
};
