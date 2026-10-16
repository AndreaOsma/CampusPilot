import { useCallback, useEffect, useState } from "react";

export type Route =
  | { name: "home" }
  | { name: "career" }
  | { name: "subject"; id: number }
  | { name: "semester" }
  | { name: "study" }
  | { name: "learn" }
  | { name: "lesson"; id: number }
  | { name: "review" }
  | { name: "practice"; courseId: number; concept: string; objective?: string }
  | { name: "exam"; courseId: number }
  | { name: "draft"; id: number }
  | { name: "inbox" }
  | { name: "money" }
  | { name: "path" }
  | { name: "modules" }
  | { name: "settings" };

const STATIC: Record<string, Route> = {
  "/": { name: "home" },
  "/expediente": { name: "career" },
  "/semestre": { name: "semester" },
  "/estudio": { name: "study" },
  "/aprender": { name: "learn" },
  "/aprender/repaso": { name: "review" },
  "/bandeja": { name: "inbox" },
  "/dinero": { name: "money" },
  "/trayectoria": { name: "path" },
  "/modulos": { name: "modules" },
  "/ajustes": { name: "settings" },
};

export function parsePath(pathname: string): Route {
  const clean = pathname.replace(/\/+$/, "") || "/";
  if (STATIC[clean]) return STATIC[clean];
  const subject = clean.match(/^\/asignaturas\/(\d+)$/);
  if (subject) return { name: "subject", id: Number(subject[1]) };
  const lesson = clean.match(/^\/aprender\/leccion\/(\d+)$/);
  if (lesson) return { name: "lesson", id: Number(lesson[1]) };
  const byObjective = clean.match(/^\/aprender\/practica\/(\d+)\/objetivo\/([^/]+)$/);
  if (byObjective) return { name: "practice", courseId: Number(byObjective[1]), concept: "", objective: decodeURIComponent(byObjective[2]) };
  const practice = clean.match(/^\/aprender\/practica\/(\d+)(?:\/(.+))?$/);
  if (practice) return { name: "practice", courseId: Number(practice[1]), concept: practice[2] ? decodeURIComponent(practice[2]) : "" };
  const exam = clean.match(/^\/aprender\/examen\/(\d+)$/);
  if (exam) return { name: "exam", courseId: Number(exam[1]) };
  const draft = clean.match(/^\/aprender\/borrador\/(\d+)$/);
  if (draft) return { name: "draft", id: Number(draft[1]) };
  return { name: "home" };
}

export function pathFor(route: Route): string {
  if (route.name === "subject") return `/asignaturas/${route.id}`;
  if (route.name === "lesson") return `/aprender/leccion/${route.id}`;
  if (route.name === "practice" && route.objective) return `/aprender/practica/${route.courseId}/objetivo/${encodeURIComponent(route.objective)}`;
  if (route.name === "practice") return `/aprender/practica/${route.courseId}${route.concept ? `/${encodeURIComponent(route.concept)}` : ""}`;
  if (route.name === "exam") return `/aprender/examen/${route.courseId}`;
  if (route.name === "draft") return `/aprender/borrador/${route.id}`;
  return Object.entries(STATIC).find(([, r]) => r.name === route.name)?.[0] ?? "/";
}

export type Navigate = (route: Route) => void;

export function useRoute() {
  const [route, setRoute] = useState<Route>(() => parsePath(window.location.pathname));

  useEffect(() => {
    const onPopState = () => setRoute(parsePath(window.location.pathname));
    window.addEventListener("popstate", onPopState);
    return () => window.removeEventListener("popstate", onPopState);
  }, []);

  const navigate = useCallback<Navigate>((next) => {
    const path = pathFor(next);
    if (path !== window.location.pathname) window.history.pushState({}, "", path);
    setRoute(next);
    window.scrollTo({ top: 0 });
  }, []);

  return { route, navigate };
}

/** Manejador de clic para <a href> internos: navega sin recargar (respeta cmd/ctrl-clic). */
export function linkTo(navigate: Navigate, route: Route) {
  return (e: React.MouseEvent) => {
    if (e.metaKey || e.ctrlKey || e.shiftKey || e.button !== 0) return;
    e.preventDefault();
    navigate(route);
  };
}
