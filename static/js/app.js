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
    const health      = reactive({ db: false, tutor: false, speech: false, tts: false });

    async function fetchHealth() {
      // fetchServiceStatus (utils/health.js) turns "ok"/"unavailable" into true/false
      Object.assign(health, await fetchServiceStatus());
      fatalError.value = !health.db;
      loading.value = false;
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
createApp(App)
  .component("service-notice", ServiceNotice)  // banner from utils/health.js
  .use(router)
  .mount("#app");
