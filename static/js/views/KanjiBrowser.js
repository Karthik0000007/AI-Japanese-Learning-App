/**
 * static/js/views/KanjiBrowser.js — Grid of kanji tiles with modal detail view.
 */
const KanjiBrowserView = {
  name: "KanjiBrowser",
  setup() {
    const { ref, watch, onMounted } = Vue;

    const items    = ref([]);
    const total    = ref(0);
    const page     = ref(1);
    const pageSize = 80;
    const search   = ref("");
    const level    = ref("");
    const loading  = ref(false);
    const selected = ref(null);  // modal
    let debounce   = null;

    async function load() {
      loading.value = true;
      const p = new URLSearchParams({ page: page.value, limit: pageSize });
      if (search.value) p.set("search", search.value);
      if (level.value)  p.set("level",  level.value);
      const res  = await fetch(`/api/kanji?${p}`);
      const data = await res.json();
      items.value = data.items ?? [];
      total.value = data.total ?? 0;
      loading.value = false;
    }

    function onSearchInput() {
      clearTimeout(debounce);
      debounce = setTimeout(() => { page.value = 1; load(); }, 350);
    }

    watch(level, () => { page.value = 1; load(); });
    onMounted(load);

    const totalPages = () => Math.ceil(total.value / pageSize);
    const prev = () => { if (page.value > 1) { page.value--; load(); } };
    const next = () => { if (page.value < totalPages()) { page.value++; load(); } };

    function openModal(k) { selected.value = k; }
    function closeModal()  { selected.value = null; }

    async function playTTS(character) {
      try {
        const res = await fetch("/api/tts", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ text: character }),
        });
        if (!res.ok) return;
        const blob = await res.blob();
        new Audio(URL.createObjectURL(blob)).play();
      } catch {}
    }

    return {
      items, total, page, search, level, loading, selected,
      onSearchInput, prev, next, totalPages, openModal, closeModal, playTTS,
    };
  },

  template: `
  <div>
    <h1 class="section-title">🈴 Kanji Browser</h1>

    <div class="flex-row" style="flex-wrap:wrap; gap:0.75rem; margin-bottom:1rem">
      <input v-model="search" @input="onSearchInput" placeholder="Kanji / meaning…" style="flex:1; min-width:160px" />
      <select v-model="level" style="width:110px">
        <option value="">All levels</option>
        <option>N5</option><option>N4</option><option>N3</option><option>N2</option><option>N1</option>
      </select>
      <span class="muted">{{ total }} kanji</span>
    </div>

    <div v-if="loading" class="muted">Loading…</div>

    <div v-else class="kanji-grid">
      <div v-for="k in items" :key="k.id" class="kanji-tile" @click="openModal(k)">
        <div class="kanji-char">{{ k.character }}</div>
        <div class="kanji-meaning">{{ (k.meaning ?? []).slice(0,2).join(', ') }}</div>
        <div style="margin-top:0.3rem">
          <span v-if="k.jlpt_level" :class="['pill', 'pill-' + k.jlpt_level]" style="font-size:0.69rem">{{ k.jlpt_level }}</span>
        </div>
      </div>
    </div>

    <div v-if="items.length === 0 && !loading" class="muted mt-2" style="text-align:center">
      No kanji found. Run <code>python tools/setup.py</code> to seed the database.
    </div>

    <div class="pagination mt-2">
      <button :disabled="page <= 1" @click="prev">‹ Prev</button>
      <span class="muted">Page {{ page }} / {{ totalPages() }}</span>
      <button :disabled="page >= totalPages()" @click="next">Next ›</button>
    </div>

    <!-- Modal -->
    <div v-if="selected" class="modal-overlay" @click.self="closeModal">
      <div class="modal-box">
        <div class="flex-row" style="justify-content:space-between; align-items:flex-start">
          <div class="modal-kanji">{{ selected.character }}</div>
          <button @click="playTTS(selected.character)" style="background:var(--surface2);color:var(--text);border:1px solid var(--border)">🔊</button>
        </div>
        <div class="mt-1">
          <span v-if="selected.jlpt_level" :class="['pill', 'pill-' + selected.jlpt_level]">{{ selected.jlpt_level }}</span>
          <span class="muted" style="margin-left:0.5rem; font-size:0.85rem">{{ selected.stroke_count }} strokes</span>
        </div>
        <div class="mt-2">
          <p><span class="muted">On-yomi:</span> {{ (selected.on_yomi ?? []).join('、') || '—' }}</p>
          <p><span class="muted">Kun-yomi:</span> {{ (selected.kun_yomi ?? []).join('、') || '—' }}</p>
          <p class="mt-1"><span class="muted">Meaning:</span> {{ (selected.meaning ?? []).join('; ') }}</p>
          <p v-if="selected.example_word" class="mt-1">
            <span class="muted">Example:</span>
            <span style="font-family:var(--font-jp)">{{ selected.example_word }}</span>
          </p>
        </div>
        <button @click="closeModal" class="mt-2" style="background:var(--surface2);color:var(--text);border:1px solid var(--border);width:100%">Close</button>
      </div>
    </div>
  </div>
  `,
};
