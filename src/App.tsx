import { lazy, Suspense, useEffect, useState } from "react";
import type { ModuleId } from "./api";
import { AppearanceToggle, type DayNightMode } from "./components/AppearanceToggle";
import { Dashboard } from "./pages/Dashboard";
import { linkTo, pathFor, useRoute, type Route } from "./router";
import { useStore } from "./store";
import { ErrorBox, Loading, readStored, UiModeContext, writeStored, type UiMode } from "./ui";
import { t } from "./i18n";

// Cada página en su propio trozo: el primer arranque solo baja «Hoy» (KaTeX, Aprender… bajo demanda).
const Career = lazy(() => import("./pages/Career").then((m) => ({ default: m.Career })));
const Learn = lazy(() => import("./pages/Learn").then((m) => ({ default: m.Learn })));
const DraftReview = lazy(() => import("./pages/DraftReview").then((m) => ({ default: m.DraftReview })));
const LessonPlayer = lazy(() => import("./pages/LessonPlayer").then((m) => ({ default: m.LessonPlayer })));
const InboxPage = lazy(() => import("./pages/Inbox").then((m) => ({ default: m.InboxPage })));
const Modules = lazy(() => import("./pages/Modules").then((m) => ({ default: m.Modules })));
const Money = lazy(() => import("./pages/Money").then((m) => ({ default: m.Money })));
const PathPage = lazy(() => import("./pages/Path").then((m) => ({ default: m.PathPage })));
const Semester = lazy(() => import("./pages/Semester").then((m) => ({ default: m.Semester })));
const SettingsPage = lazy(() => import("./pages/Settings").then((m) => ({ default: m.SettingsPage })));
const Study = lazy(() => import("./pages/Study").then((m) => ({ default: m.Study })));
const SubjectDetail = lazy(() => import("./pages/SubjectDetail").then((m) => ({ default: m.SubjectDetail })));

type NavItem = { route: Route; label: string; icon: string; primary?: boolean; module?: ModuleId };

const NAV: NavItem[] = [
  { route: { name: "home" }, label: t("Hoy"), icon: "🏠", primary: true },
  { route: { name: "career" }, label: t("Expediente"), icon: "🎓", primary: true },
  { route: { name: "semester" }, label: t("Semestre"), icon: "🗓️", primary: true, module: "semestre" },
  { route: { name: "learn" }, label: t("Aprender"), icon: "🎯", primary: true, module: "aprender" },
  { route: { name: "inbox" }, label: t("Bandeja"), icon: "📥", module: "bandeja" },
  { route: { name: "study" }, label: t("Estudio"), icon: "🧠", module: "estudio" },
  { route: { name: "money" }, label: t("Dinero y trámites"), icon: "💶", module: "dinero" },
  { route: { name: "path" }, label: t("Trayectoria"), icon: "🧭", module: "trayectoria" },
  { route: { name: "modules" }, label: t("Módulos"), icon: "🧩" },
  { route: { name: "settings" }, label: t("Ajustes"), icon: "⚙️" },
];

function sectionOf(route: Route): Route["name"] {
  if (route.name === "subject") return "career";
  if (["lesson", "review", "practice", "exam", "draft"].includes(route.name)) return "learn";
  return route.name;
}

export default function App() {
  const { route, navigate } = useRoute();
  const { settings, error, reload } = useStore();
  const [moreOpen, setMoreOpen] = useState(false);

  const [dayNightMode, setDayNightMode] = useState<DayNightMode>(() =>
    readStored("campus-daynight", "auto", ["day", "night", "auto"] as const)
  );
  const [uiMode, setUiMode] = useState<UiMode>(() => readStored("campus-uimode", "minimal", ["minimal", "detailed"] as const));
  const [systemDark, setSystemDark] = useState(() => window.matchMedia("(prefers-color-scheme: dark)").matches);

  useEffect(() => writeStored("campus-daynight", dayNightMode), [dayNightMode]);
  useEffect(() => writeStored("campus-uimode", uiMode), [uiMode]);
  const [toast, setToast] = useState<string | null>(null);
  const changeMode = (m: UiMode) => {
    if (m === uiMode) return;
    setUiMode(m);
    setToast(m === "detailed" ? t("Vista detallada: más información y opciones avanzadas") : t("Vista mínima: solo lo esencial"));
  };
  useEffect(() => {
    if (!toast) return;
    const t = window.setTimeout(() => setToast(null), 2600);
    return () => window.clearTimeout(t);
  }, [toast]);

  useEffect(() => {
    const mq = window.matchMedia("(prefers-color-scheme: dark)");
    const sync = () => setSystemDark(mq.matches);
    mq.addEventListener("change", sync);
    return () => mq.removeEventListener("change", sync);
  }, []);

  const effectiveDark = dayNightMode === "night" ? true : dayNightMode === "day" ? false : systemDark;

  useEffect(() => {
    document.documentElement.dataset.theme = effectiveDark ? "dark" : "light";
    document.querySelector('meta[name="theme-color"]')?.setAttribute("content", effectiveDark ? "#0d0f1f" : "#f1f0fb");
  }, [effectiveDark]);

  useEffect(() => setMoreOpen(false), [route]);
  // Hoja «Más»: Escape la cierra y el foco entra en ella al abrirse y vuelve al botón al cerrarse.
  useEffect(() => {
    if (!moreOpen) return;
    const trigger = document.activeElement as HTMLElement | null;
    document.querySelector<HTMLElement>("#more-sheet a, #more-sheet button")?.focus();
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && setMoreOpen(false);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("keydown", onKey);
      trigger?.focus?.();
    };
  }, [moreOpen]);

  const enabled = (item: NavItem) => !item.module || settings?.modules[item.module] !== false;
  const nav = NAV.filter(enabled);
  const current = sectionOf(route);
  const disabledRoute = NAV.find((n) => n.route.name === current && !enabled(n));

  const navLink = (item: NavItem, className: string) => (
    <a
      key={item.route.name}
      href={pathFor(item.route)}
      className={`${className}${current === item.route.name ? " is-active" : ""}`}
      aria-current={current === item.route.name ? "page" : undefined}
      title={item.label}
      onClick={linkTo(navigate, item.route)}
    >
      <span aria-hidden className={`${className}__icon`}>
        {item.icon}
      </span>
      <span className={`${className}__label`}>{item.label}</span>
    </a>
  );

  return (
    <UiModeContext.Provider value={uiMode}>
      <div
        className={`app-shell ${effectiveDark ? "theme-dark" : "theme-light"} mode-${uiMode}${["lesson", "review", "practice", "exam"].includes(route.name) ? " is-focus" : ""}`}
      >
        <a href="#main" className="skip-link">
          {t("Saltar al contenido")}
        </a>
        <header className="app-header">
          <a href="/" className="app-header__brand" onClick={linkTo(navigate, { name: "home" })}>
            <span aria-hidden>🎓</span> {t("Campus Pilot")}
          </a>
          <nav className="top-nav" aria-label={t("Secciones")}>
            {nav.map((item) => navLink(item, "top-nav__link"))}
          </nav>
          <div className="app-header__controls">
            <div className="segmented" role="group" aria-label={t("Densidad de la interfaz")}>
              {(["minimal", "detailed"] as const).map((m) => (
                <button key={m} type="button" className={uiMode === m ? "is-active" : ""} aria-pressed={uiMode === m} onClick={() => changeMode(m)}>
                  {m === "minimal" ? t("Mínimo") : t("Detalle")}
                </button>
              ))}
            </div>
            <AppearanceToggle value={dayNightMode} onChange={setDayNightMode} />
          </div>
        </header>

        <main id="main" className="app-main">
          {error && <ErrorBox message={error} onRetry={() => void reload()} />}
          {disabledRoute ? (
            <div className="card">
              <p>
                {t("El módulo")} <strong>{disabledRoute.label}</strong> {t("está desactivado. Puedes activarlo en")}{" "}
                <a href="/modulos" onClick={linkTo(navigate, { name: "modules" })}>
                  {t("Módulos")}
                </a>
                .
              </p>
            </div>
          ) : (
            <Suspense fallback={<Loading />}>
              {route.name === "home" && <Dashboard navigate={navigate} />}
              {route.name === "career" && <Career navigate={navigate} />}
              {route.name === "subject" && <SubjectDetail navigate={navigate} subjectId={route.id} />}
              {route.name === "semester" && <Semester navigate={navigate} />}
              {route.name === "study" && <Study />}
              {route.name === "learn" && <Learn navigate={navigate} />}
              {route.name === "lesson" && <LessonPlayer navigate={navigate} mode={{ kind: "lesson", lessonId: route.id }} />}
              {route.name === "review" && <LessonPlayer navigate={navigate} mode={{ kind: "review" }} />}
              {route.name === "practice" && (
                <LessonPlayer navigate={navigate} mode={{ kind: "practice", courseId: route.courseId, concept: route.concept, objective: route.objective }} />
              )}
              {route.name === "exam" && <LessonPlayer navigate={navigate} mode={{ kind: "exam", courseId: route.courseId }} />}
              {route.name === "draft" && <DraftReview navigate={navigate} jobId={route.id} />}
              {route.name === "inbox" && <InboxPage />}
              {route.name === "money" && <Money />}
              {route.name === "path" && <PathPage />}
              {route.name === "modules" && <Modules navigate={navigate} />}
              {route.name === "settings" && <SettingsPage />}
            </Suspense>
          )}
        </main>

        {toast && (
          <div className="toast" role="status">
            {toast}
          </div>
        )}
        <footer className="app-footer muted">
          © {new Date().getFullYear()}{" "}
          <a href="https://andreaosma.com" target="_blank" rel="noreferrer">
            {t("Andrea Osma Rafael")}
          </a>
        </footer>

        <nav className="bottom-nav" aria-label={t("Secciones principales")}>
          {nav.filter((n) => n.primary).map((item) => navLink(item, "bottom-nav__link"))}
          <button
            type="button"
            className={`bottom-nav__link${!nav.find((n) => n.primary && n.route.name === current) ? " is-active" : ""}`}
            aria-expanded={moreOpen}
            aria-controls="more-sheet"
            onClick={() => setMoreOpen((v) => !v)}
          >
            <span aria-hidden className="bottom-nav__link__icon">
              ☰
            </span>
            <span className="bottom-nav__link__label">{t("Más")}</span>
          </button>
        </nav>
        {moreOpen && (
          <>
            <div className="sheet-backdrop" onClick={() => setMoreOpen(false)} aria-hidden />
            <nav id="more-sheet" className="more-sheet" aria-label={t("Más secciones")}>
              {nav.filter((n) => !n.primary).map((item) => navLink(item, "more-sheet__link"))}
            </nav>
          </>
        )}
      </div>
    </UiModeContext.Provider>
  );
}
