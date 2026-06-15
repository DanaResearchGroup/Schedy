import { useEffect, useMemo, useState } from "react";
import { api } from "./api";
import type { Course, FixedEvent, Placement, SessionMeta, Violation } from "./types";
import { ROOMS } from "./types";
import { boxLabel, DAY_NAMES, ROLE_LABEL, t, type Lang } from "./i18n";
import { WeeklyGrid } from "./components/WeeklyGrid";
import { RoomBoards } from "./components/RoomBoards";
import { CatalogPanel } from "./components/CatalogPanel";
import { ImportPanel } from "./components/ImportPanel";
import { AvailabilityPanel } from "./components/AvailabilityPanel";
import { CalendarPanel } from "./components/CalendarPanel";

type Tab = "schedule" | "catalog" | "availability" | "calendar" | "import";

const ROOM_NAME: Record<string, string> =
  Object.fromEntries(ROOMS.map((r) => [r.id, r.name.split(" (")[0]]));

function timeRange(startBox: number, len: number): string {
  const a = boxLabel(startBox).split("-")[0];
  const b = boxLabel(startBox + Math.max(1, len) - 1).split("-")[1];
  return `${a}-${b}`;
}

const TABS = ["schedule", "catalog", "availability", "calendar", "import"] as const;
const TAB_KEY = {
  schedule: "tabSchedule",
  catalog: "tabCatalog",
  availability: "tabAvailability",
  calendar: "tabCalendar",
  import: "tabImport",
} as const;

export default function App() {
  const [lang, setLang] = useState<Lang>("he");
  const [tab, setTab] = useState<Tab>("schedule");
  const [courses, setCourses] = useState<Course[]>([]);
  const [placements, setPlacements] = useState<Record<string, Placement> | null>(null);
  const [sessions, setSessions] = useState<Record<string, SessionMeta>>({});
  const [walls, setWalls] = useState<FixedEvent[]>([]);
  const [violations, setViolations] = useState<Violation[]>([]);
  const [solving, setSolving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [view, setView] = useState<string>("all");
  const [layout, setLayout] = useState<"grid" | "rooms">("grid");
  const [selected, setSelected] = useState<string | null>(null);

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
        setSessions(r.sessions);
        setViolations(r.violations);
        setSelected(null);
        api.fixedEvents().then(setWalls).catch(() => setWalls([]));
      } else setError(`No solution (${r.status})`);
    } catch (e) {
      setError(String(e));
    } finally {
      setSolving(false);
    }
  };

  // room is supplied by the per-room boards (drag across cards reassigns it);
  // the weekly grid omits it and the session keeps its current room.
  const onMove = async (sid: string, day: number, startBox: number, room?: string) => {
    if (!placements) return;
    const next = {
      ...placements,
      [sid]: { ...placements[sid], day, start_box: startBox, ...(room ? { room_id: room } : {}) },
    };
    setPlacements(next);
    try {
      const r = await api.evaluate(next);
      setViolations(r.violations);
    } catch (e) {
      setError(String(e));
    }
  };

  // Park a session: drop it from all rooms (unplaced) so it can be set aside
  // while rebalancing. Re-validate without it; Solve re-places everything.
  const onPark = async (sid: string) => {
    if (!placements) return;
    const next = { ...placements };
    delete next[sid];
    setPlacements(next);
    if (selected === sid) setSelected(null);
    try {
      const r = await api.evaluate(next);
      setViolations(r.violations);
    } catch (e) {
      setError(String(e));
    }
  };

  // Sessions with no current placement — shown in the Parked lane (rooms view).
  const parked = useMemo(
    () => (placements ? Object.keys(sessions).filter((sid) => !placements[sid]) : []),
    [sessions, placements],
  );

  // View filter: which sessions to show on the grid.
  const { cohorts, rooms, lecturers } = useMemo(() => {
    const co = new Set<string>(), rm = new Set<string>(), le = new Set<string>();
    for (const [sid, m] of Object.entries(sessions)) {
      m.cohorts.forEach((c) => co.add(c));
      m.lecturers.forEach((l) => le.add(l));
      if (placements?.[sid]) rm.add(placements[sid].room_id);
    }
    return { cohorts: [...co].sort(), rooms: [...rm].sort(), lecturers: [...le].sort() };
  }, [sessions, placements]);

  const shownPlacements = useMemo(() => {
    if (!placements || view === "all") return placements ?? {};
    const [kind, val] = view.split(":");
    const out: Record<string, Placement> = {};
    for (const [sid, p] of Object.entries(placements)) {
      const m = sessions[sid];
      const keep =
        kind === "cohort" ? m?.cohorts.includes(val)
        : kind === "room" ? p.room_id === val
        : kind === "lecturer" ? m?.lecturers.includes(val)
        : true;
      if (keep) out[sid] = p;
    }
    return out;
  }, [placements, sessions, view]);

  // Blackouts are global; external-course walls belong to cohorts. Filter them
  // to match the active view so the overlay stays consistent with the blocks.
  const shownWalls = useMemo(() => {
    if (view === "all") return walls;
    const [kind, val] = view.split(":");
    return walls.filter((w) =>
      w.kind === "blackout" ? true
      : kind === "cohort" ? w.cohorts.includes(val)
      : false);
  }, [walls, view]);

  const hardCount = violations.filter((v) => v.severity === "hard").length;
  const selectedViolations = selected
    ? violations.filter((v) => v.session_ids.includes(selected))
    : [];

  return (
    <div className="app">
      <header>
        <div className="brand">⬡ <strong>Schedy</strong></div>
        <nav className="tabs">
          {TABS.map((tb) => (
            <button key={tb} className={tab === tb ? "tab active" : "tab"}
              onClick={() => setTab(tb)}>
              {t(TAB_KEY[tb], lang)}
            </button>
          ))}
        </nav>
        <div className="spacer" />
        <button className="ghost" onClick={() => setLang(lang === "he" ? "en" : "he")}>
          {lang === "he" ? "EN" : "עב"}
        </button>
      </header>

      {error && <div className="error">{error}</div>}

      {tab === "catalog" && (
        <div className="panel">
          <CatalogPanel
            courses={courses} lang={lang}
            onAdd={(c) => api.upsertCourse(c).then(refresh).catch((e) => setError(String(e)))}
            onDelete={(n) => api.deleteCourse(n).then(refresh)}
            onSeed={() => api.seedCatalog().then(refresh).catch((e) => setError(String(e)))}
          />
        </div>
      )}

      {tab === "availability" && (
        <div className="panel"><AvailabilityPanel courses={courses} lang={lang} /></div>
      )}

      {tab === "calendar" && <div className="panel"><CalendarPanel lang={lang} /></div>}

      {tab === "import" && <div className="panel"><ImportPanel lang={lang} /></div>}

      {tab === "schedule" && (
        <div className="panel">
          <div className="toolbar">
            <button className="primary" disabled={solving} onClick={solve}>
              {solving ? t("solving", lang) : t("solve", lang)}
            </button>
            {placements && (
              <>
                <div className="seg" role="group">
                  <button className={layout === "grid" ? "seg-btn active" : "seg-btn"}
                    onClick={() => setLayout("grid")}>{t("layoutGrid", lang)}</button>
                  <button className={layout === "rooms" ? "seg-btn active" : "seg-btn"}
                    onClick={() => setLayout("rooms")}>{t("layoutRooms", lang)}</button>
                </div>
                {layout === "grid" && (
                  <label className="view">
                    {t("view", lang)}:
                    <select value={view} onChange={(e) => setView(e.target.value)}>
                      <option value="all">{t("allSessions", lang)}</option>
                      <optgroup label={t("byCohort", lang)}>
                        {cohorts.map((c) => <option key={c} value={`cohort:${c}`}>{c}</option>)}
                      </optgroup>
                      <optgroup label={t("byRoom", lang)}>
                        {rooms.map((r) => <option key={r} value={`room:${r}`}>{r}</option>)}
                      </optgroup>
                      <optgroup label={t("byLecturer", lang)}>
                        {lecturers.map((l) => <option key={l} value={`lecturer:${l}`}>{l}</option>)}
                      </optgroup>
                    </select>
                  </label>
                )}
                <div className="spacer" />
                {parked.length > 0 && (
                  <button className="badge warn" title={t("unplacedHint", lang)}
                    onClick={() => setLayout("rooms")}>
                    {parked.length} {t("unplaced", lang)}
                  </button>
                )}
                <span className={hardCount ? "badge bad" : "badge ok"}>
                  {hardCount ? `${hardCount} ⚠` : t("feasible", lang)}
                </span>
                <a className="ghost" href={api.exportCsvUrl()}>CSV</a>
                <a className="ghost" href={api.exportPdfUrl("cohort")}>{t("pdfGrid", lang)}</a>
                <a className="ghost" href={api.exportPdfUrl("flat")}>{t("pdfList", lang)}</a>
              </>
            )}
          </div>

          {placements ? (
            <div className="schedule-body">
              <div className="grid-wrap">
                {layout === "rooms" ? (
                  <RoomBoards
                    placements={placements} sessions={sessions} violations={violations}
                    walls={walls} parked={parked} lang={lang} selectedId={selected}
                    onMove={onMove} onPark={onPark} onSelect={setSelected}
                  />
                ) : (
                  <WeeklyGrid
                    placements={shownPlacements} sessions={sessions} violations={violations}
                    walls={shownWalls} lang={lang} selectedId={selected}
                    onMove={onMove} onSelect={setSelected}
                  />
                )}
                <div className="legend">
                  {(["core", "elective", "replacement", "lab"] as const).map((r) => (
                    <span key={r} className="leg-item">
                      <span className={`leg-swatch role-${r}`} />{ROLE_LABEL[r][lang]}
                    </span>
                  ))}
                  <span className="leg-item"><span className="leg-swatch leg-wall-bk" />{t("blackoutLegend", lang)}</span>
                  <span className="leg-item"><span className="leg-swatch leg-wall-ext" />{t("externalLegend", lang)}</span>
                </div>
              </div>
              <aside className="detail">
                {selected ? (
                  <>
                    {(() => {
                      const m = sessions[selected];
                      const p = placements?.[selected];
                      const course = courses.find((c) => c.number === m?.course_number);
                      const name = course && (lang === "he" ? course.name_he : course.name_en);
                      return (
                        <>
                          <h3>
                            {name || m?.course_number || selected}
                            {m?.fixed && <span title={t("fixedTag", lang)}> 🔒</span>}
                          </h3>
                          {m && (
                            <ul className="meta">
                              <li>{m.course_number} · {m.type}{m.group ? ` · ${m.group}` : ""}</li>
                              {p && (
                                <li>🗓 {DAY_NAMES[lang][p.day]} {timeRange(p.start_box, m.length_boxes)}</li>
                              )}
                              {p && <li>📍 {ROOM_NAME[p.room_id] ?? p.room_id}</li>}
                              <li>{m.cohorts.join(", ")}</li>
                              {m.lecturers.length > 0 && <li>👤 {m.lecturers.join(", ")}</li>}
                              {m.tas.length > 0 && <li>🎓 {m.tas.join(", ")}</li>}
                            </ul>
                          )}
                        </>
                      );
                    })()}
                    {selectedViolations.length > 0 ? (
                      <ul className="violations">
                        {selectedViolations.map((v, i) => (
                          <li key={i} className={v.severity}>
                            <span className="kind">{v.kind}</span> {v.message}
                          </li>
                        ))}
                      </ul>
                    ) : <p className="muted ok-text">✓ {t("noViolations", lang)}</p>}
                  </>
                ) : (
                  <p className="muted">{t("details", lang)}</p>
                )}
              </aside>
            </div>
          ) : (
            <div className="empty">
              <p>{t("empty", lang)}</p>
              {courses.length === 0 && (
                <button className="ghost" onClick={async () => {
                  try {
                    await api.seedCatalog();
                    await refresh();
                    await solve();
                  } catch (e) { setError(String(e)); }
                }}>{t("loadSample", lang)}</button>
              )}
            </div>
          )}

          {violations.length > 0 && (
            <section className="violations all-violations">
              <h3>{t("violations", lang)} ({violations.length})</h3>
              <ul>
                {violations.map((v, i) => (
                  <li key={i} className={v.severity}
                    onClick={() => v.session_ids[0] && setSelected(v.session_ids[0])}>
                    <span className="kind">{v.kind}</span> {v.message}
                  </li>
                ))}
              </ul>
            </section>
          )}
        </div>
      )}
    </div>
  );
}
