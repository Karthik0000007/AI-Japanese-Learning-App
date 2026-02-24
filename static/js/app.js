/**
 * static/js/app.js — Vue 3 application bootstrap + router.
 */
const { createApp, ref, reactive, onMounted } = Vue;
const { createRouter, createWebHistory } = VueRouter;

// ── Router ────────────────────────────────────────────────────────────────────
const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: "/",           component: DashboardView },
    { path: "/flashcards", component: FlashcardsView },
    { path: "/vocab",      component: VocabBrowserView },
    { path: "/kanji",      component: KanjiBrowserView },
    { path: "/tutor",      component: TutorView },
    { path: "/progress",   component: ProgressView },
  ],
});

// ── Root component ─────────────────────────────────────────────────────────────
const App = {
  setup() {
    const loading     = ref(true);
    const fatalError  = ref(false);
    const health      = reactive({ db: false, ollama: false, piper: false });

    async function fetchHealth() {
      try {
        const res = await fetch("/api/health");
        if (!res.ok) throw new Error("health endpoint failed");
        const data = await res.json();
        health.db     = data.db;
        health.ollama = data.ollama;
        health.piper  = data.piper;
        fatalError.value = !data.db;
      } catch {
        fatalError.value = true;
      } finally {
        loading.value = false;
      }
    }

    onMounted(() => {
      fetchHealth();
      // Refresh health indicator every 30 s
      setInterval(fetchHealth, 30_000);
    });

    return { loading, fatalError, health };
  },

  template: document.getElementById("app").innerHTML,
};

// ── Mount ──────────────────────────────────────────────────────────────────────
createApp(App).use(router).mount("#app");
