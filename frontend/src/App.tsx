import { useEffect, useState } from "react";
import { api } from "./api";
import type { Course, Placement, Violation } from "./types";
import { t, type Lang } from "./i18n";
import { WeeklyGrid } from "./components/WeeklyGrid";
import { CatalogPanel } from "./components/CatalogPanel";

export default function App() {
  const [lang, setLang] = useState<Lang>("he");
  const [courses, setCourses] = useState<Course[]>([]);
  const [placements, setPlacements] = useState<Record<string, Placement> | null>(null);
  const [violations, setViolations] = useState<Violation[]>([]);
  const [solving, setSolving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    document.documentElement.dir = lang === "he" ? "rtl" : "ltr";
    document.documentElement.lang = lang;
  }, [lang]);

  const refresh = () => api.listCourses().then(setCourses).catch((e) => setError(String(e)));
  useEffect(() => { refresh(); }, []);

  const solve = async () => {
    setSolving(true);
    setError(null);
    try {
      const r = await api.solve(10);
      if (r.solved) {
        setPlacements(r.placements);
        setViolations(r.violations);
      } else {
        setError(`No solution (${r.status})`);
      }
    } catch (e) {
      setError(String(e));
    } finally {
      setSolving(false);
    }
  };

  // Drag-drop edit: move a session to a new cell (keeping its room), then ask the
  // backend to re-validate the whole schedule live — the editor backstop.
  const onMove = async (sid: string, day: number, startBox: number) => {
    if (!placements) return;
    const next = { ...placements, [sid]: { ...placements[sid], day, start_box: startBox } };
    setPlacements(next);
    try {
      const r = await api.evaluate(next);
      setViolations(r.violations);
    } catch (e) {
      setError(String(e));
    }
  };

  const hardCount = violations.filter((v) => v.severity === "hard").length;

  return (
    <div className="app">
      <header>
        <h1>{t("title", lang)}</h1>
        <div className="spacer" />
        <button onClick={() => setLang(lang === "he" ? "en" : "he")}>
          {lang === "he" ? "English" : "עברית"}
        </button>
      </header>

      {error && <div className="error">{error}</div>}

      <div className="layout">
        <aside>
          <CatalogPanel
            courses={courses}
            lang={lang}
            onAdd={(c) => api.upsertCourse(c).then(refresh)}
            onDelete={(n) => api.deleteCourse(n).then(refresh)}
          />
        </aside>

        <main>
          <div className="toolbar">
            <button className="primary" disabled={solving} onClick={solve}>
              {solving ? t("solving", lang) : t("solve", lang)}
            </button>
            {placements && (
              <>
                <a href={api.exportCsvUrl()}>{t("exportCsv", lang)}</a>
                <a href={api.exportPdfUrl()}>{t("exportPdf", lang)}</a>
                <span className={hardCount ? "badge bad" : "badge ok"}>
                  {hardCount ? t("infeasible", lang) : t("feasible", lang)}
                </span>
              </>
            )}
          </div>

          <h2>{t("schedule", lang)}</h2>
          {placements ? (
            <WeeklyGrid
              placements={placements}
              violations={violations}
              lang={lang}
              onMove={onMove}
            />
          ) : (
            <p className="empty">{t("empty", lang)}</p>
          )}

          {violations.length > 0 && (
            <section className="violations">
              <h2>{t("violations", lang)}</h2>
              <ul>
                {violations.map((v, i) => (
                  <li key={i} className={v.severity}>
                    <span className="kind">{v.kind}</span> {v.message}
                  </li>
                ))}
              </ul>
            </section>
          )}
        </main>
      </div>
    </div>
  );
}
