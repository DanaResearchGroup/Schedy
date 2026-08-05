import { useEffect, useMemo, useState } from "react";
import { api } from "./api";
import type {
  Course, FixedEvent, Placement, SessionMeta, TermList, Violation,
} from "./types";
import { parseSemester, ROOMS } from "./types";
import { boxLabel, DAY_NAMES, ROLE_LABEL, t, termLabel, type Lang } from "./i18n";
import { WeeklyGrid } from "./components/WeeklyGrid";
import { RoomBoards } from "./components/RoomBoards";
import { canDrop } from "./dropCheck";
import { CatalogPanel } from "./components/CatalogPanel";
import { MultiSelect } from "./components/MultiSelect";
import {
  COURSE_GROUPS, GRAD_AUDIENCE, NO_FILTER, filterCount, filterPlacements, filterWalls,
  type GridFilter,
} from "./gridFilter";
import { ImportPanel } from "./components/ImportPanel";
import { AvailabilityPanel } from "./components/AvailabilityPanel";
import { CalendarPanel } from "./components/CalendarPanel";
import { SchedulesPanel } from "./components/SchedulesPanel";
import { ChecklistPanel } from "./components/ChecklistPanel";
import { PeoplePanel } from "./components/PeoplePanel";
import type { SolveResult } from "./types";

type Tab =
  | "schedule" | "catalog" | "people" | "availability" | "calendar"
  | "import" | "checklist" | "schedules";

const ROOM_NAME: Record<string, string> =
  Object.fromEntries(ROOMS.map((r) => [r.id, r.name.split(" (")[0]]));

function timeRange(startBox: number, len: number): string {
  const a = boxLabel(startBox).split("-")[0];
  const b = boxLabel(startBox + Math.max(1, len) - 1).split("-")[1];
  return `${a}-${b}`;
}

const TABS = ["schedule", "catalog", "people", "availability", "calendar", "import", "checklist", "schedules"] as const;
const TAB_KEY = {
  schedule: "tabSchedule",
  catalog: "tabCatalog",
  people: "tabPeople",
  availability: "tabAvailability",
  calendar: "tabCalendar",
  import: "tabImport",
  checklist: "tabChecklist",
  schedules: "tabSchedules",
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
  const [saveMsg, setSaveMsg] = useState<string | null>(null);
  const [filter, setFilter] = useState<GridFilter>(NO_FILTER);
  const [notice, setNotice] = useState<string | null>(null);
  const [terms, setTerms] = useState<TermList | null>(null);
  const [publishDrift, setPublishDrift] = useState<string | null>(null);
  const [layout, setLayout] = useState<"grid" | "rooms">("grid");
  const [selected, setSelected] = useState<string | null>(null);
  // Undo/redo stack of placement snapshots; idx points at the current state.
  const [hist, setHist] = useState<{ stack: Record<string, Placement>[]; idx: number }>(
    { stack: [], idx: -1 },
  );

  useEffect(() => {
    document.documentElement.dir = lang === "he" ? "rtl" : "ltr";
    document.documentElement.lang = lang;
  }, [lang]);

  const refresh = () => api.listCourses().then(setCourses).catch((e) => setError(String(e)));
  const refreshTerms = () => api.listTerms().then(setTerms).catch((e) => setError(String(e)));
  useEffect(() => { refresh(); refreshTerms(); }, []);

  // Ctrl/Cmd+Z to undo, Ctrl+Y or Ctrl/Cmd+Shift+Z to redo (Schedule tab only).
  useEffect(() => {
    if (tab !== "schedule") return;
    const onKey = (e: KeyboardEvent) => {
      if (!(e.ctrlKey || e.metaKey)) return;
      const k = e.key.toLowerCase();
      if (k === "z" && !e.shiftKey) { e.preventDefault(); undo(); }
      else if (k === "y" || (k === "z" && e.shiftKey)) { e.preventDefault(); redo(); }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  });

  // Paint a solved/loaded schedule onto the grid (shared by Solve and Load).
  const applyResult = (r: SolveResult) => {
    setPlacements(r.placements);
    setSessions(r.sessions);
    setViolations(r.violations);
    setSelected(null);
    setHist({ stack: [r.placements], idx: 0 }); // a fresh schedule resets history
    api.fixedEvents().then(setWalls).catch(() => setWalls([]));
    // Neither of these breaks a scheduling rule, so nothing else would say it:
    // a published session can leave the catalog, or the university can move its
    // hour, and the frozen week quietly stops matching what was released.
    const drift = [
      r.published_missing?.length
        ? t("publishedMissing", lang, { ids: r.published_missing.join(", ") })
        : "",
      r.published_conflicts?.length
        ? t("publishedConflict", lang,
            { ids: r.published_conflicts.map((c) => c.session_id).join(", ") })
        : "",
    ].filter(Boolean);
    setPublishDrift(drift.length ? drift.join(" ") : null);
  };

  const evaluateAndSet = async (next: Record<string, Placement>) => {
    try {
      const r = await api.evaluate(next);
      setViolations(r.violations);
    } catch (e) {
      setError(String(e));
    }
  };

  // Apply an edit and record it on the undo stack (truncating any redo tail).
  const commit = (next: Record<string, Placement>) => {
    setPlacements(next);
    setHist((h) => ({ stack: [...h.stack.slice(0, h.idx + 1), next], idx: h.idx + 1 }));
    evaluateAndSet(next);
  };

  const undo = () => {
    if (hist.idx <= 0) return;
    const idx = hist.idx - 1;
    const p = hist.stack[idx];
    setHist({ ...hist, idx });
    setPlacements(p);
    setSelected(null);
    evaluateAndSet(p);
  };

  const redo = () => {
    if (hist.idx >= hist.stack.length - 1) return;
    const idx = hist.idx + 1;
    const p = hist.stack[idx];
    setHist({ ...hist, idx });
    setPlacements(p);
    setSelected(null);
    evaluateAndSet(p);
  };
  const canUndo = hist.idx > 0;
  const canRedo = hist.idx < hist.stack.length - 1;

  const solve = async () => {
    setSolving(true);
    setError(null);
    try {
      const r = await api.solve(10);
      if (r.solved) applyResult(r);
      else setError(`No solution (${r.status})`);
    } catch (e) {
      setError(String(e));
    } finally {
      setSolving(false);
    }
  };

  // Toolbar shortcut: save the current schedule under a name (a managed file).
  const saveCurrent = async () => {
    const name = window.prompt(t("scheduleName", lang));
    if (name == null || !name.trim()) return;
    try {
      await api.saveSchedule(name.trim());
      setError(null);
      setSaveMsg(t("saved", lang));
      window.setTimeout(() => setSaveMsg(null), 2000);
    } catch (e) {
      setError(String(e));
    }
  };

  // Everything on screen belongs to one term. Whatever replaces that term —
  // a reset or a switch — has to clear it, or last term's plan stays visible
  // over this term's catalog. The grid filter goes too: it names this term's
  // courses, rooms and lecturers.
  const clearWorkingView = () => {
    setPlacements(null);
    setSessions({});
    setWalls([]);
    setViolations([]);
    setSelected(null);
    setHist({ stack: [], idx: -1 });
    setFilter(NO_FILTER);
    setError(null);
    setPublishDrift(null);
  };

  const flash = (msg: string) => {
    setNotice(msg);
    window.setTimeout(() => setNotice(null), 2500);
  };

  // Erase everything and return to a first-run state. Destructive with no undo,
  // so the planner has to approve it first; the API demands its own confirm too.
  const resetAll = async () => {
    const label = terms ? termLabel(terms.current, lang) : "";
    if (!window.confirm(t("resetConfirm", lang, { term: label }))) return;
    try {
      await api.reset();
      clearWorkingView();
      await refresh();
      setTab("schedule");
      flash(t("resetDone", lang));
    } catch (e) {
      setError(String(e));
    }
  };

  // ---- terms ---------------------------------------------------------- //
  const createTerm = async () => {
    const year = window.prompt(t("newTermPrompt", lang), "")?.trim();
    if (!year) return;
    const raw = window.prompt(t("newTermSemester", lang), "winter");
    if (raw == null) return;
    const semester = parseSemester(raw);
    if (!semester) { setError(t("semesterUnrecognised", lang)); return; }
    try {
      const created = await api.createTerm(year, semester);
      // Created empty and not current; opening it is the planner's next move.
      await api.setCurrentTerm(created.id);
      clearWorkingView();
      await Promise.all([refresh(), refreshTerms()]);
      setTab("catalog");
    } catch (e) {
      setError(String(e));
    }
  };

  const switchTerm = async (id: string) => {
    if (id === "__new__") return createTerm();
    if (!terms || id === terms.current) return;
    try {
      await api.setCurrentTerm(id);
      clearWorkingView();
      await Promise.all([refresh(), refreshTerms()]);
      setTab("schedule");
    } catch (e) {
      setError(String(e));
    }
  };

  // Freezing the week is the promise made to students, so it is an explicit act
  // rather than a consequence of solving.
  const currentTerm = terms?.terms.find((x) => x.id === terms.current) ?? null;

  const publishTerm = async () => {
    if (!terms) return;
    const label = termLabel(terms.current, lang);
    if (!window.confirm(t("publishConfirm", lang, { term: label }))) return;
    try {
      const r = await api.publishTerm(terms.current);
      await refreshTerms();
      flash(t("publishDone", lang, { n: String(r.frozen) }));
    } catch (e) {
      setError(String(e));
    }
  };

  const unpublishTerm = async () => {
    if (!terms) return;
    const label = termLabel(terms.current, lang);
    if (!window.confirm(t("unpublishConfirm", lang, { term: label }))) return;
    try {
      await api.unpublishTerm(terms.current);
      await refreshTerms();
    } catch (e) {
      setError(String(e));
    }
  };

  // Also how a migration's guessed term name gets confirmed or corrected.
  const renameCurrentTerm = async () => {
    if (!terms) return;
    const cur = terms.terms.find((x) => x.id === terms.current);
    if (!cur) return;
    const year = window.prompt(t("newTermPrompt", lang), cur.year)?.trim();
    if (!year) return;
    const raw = window.prompt(t("newTermSemester", lang), cur.semester);
    if (raw == null) return;
    const semester = parseSemester(raw);
    if (!semester) { setError(t("semesterUnrecognised", lang)); return; }
    try {
      await api.renameTerm(cur.id, year, semester);
      await refreshTerms();
    } catch (e) {
      setError(String(e));
    }
  };

  // room is supplied by the per-room boards (drag across cards reassigns it);
  // the weekly grid omits it and the session keeps its current room.
  const onMove = (sid: string, day: number, startBox: number, room?: string) => {
    if (!placements) return;
    commit({
      ...placements,
      [sid]: { ...placements[sid], day, start_box: startBox, ...(room ? { room_id: room } : {}) },
    });
  };

  // Live drop-validity preview for the grids (room defaults to the session's
  // current room when not reassigning).
  const validateDrop = (sid: string, day: number, box: number, room?: string) =>
    placements
      ? canDrop(sid, day, box, room ?? placements[sid]?.room_id, placements, sessions, walls)
      : true;

  // Park a session: drop it from all rooms (unplaced) so it can be set aside
  // while rebalancing. Re-validate without it; Solve re-places everything.
  const onPark = (sid: string) => {
    if (!placements) return;
    const next = { ...placements };
    delete next[sid];
    if (selected === sid) setSelected(null);
    commit(next);
  };

  // Sessions with no current placement — shown in the Parked lane (rooms view).
  const parked = useMemo(
    () => (placements ? Object.keys(sessions).filter((sid) => !placements[sid]) : []),
    [sessions, placements],
  );

  // Filter choices offered by the current schedule. The course groups and the
  // graduate audience are a fixed taxonomy, so they live in gridFilter.ts.
  const { cohorts, rooms, lecturers } = useMemo(() => {
    const co = new Set<string>(), rm = new Set<string>(), le = new Set<string>();
    for (const [sid, m] of Object.entries(sessions)) {
      m.cohorts.forEach((c) => co.add(c));
      m.lecturers.forEach((l) => le.add(l));
      if (placements?.[sid]) rm.add(placements[sid].room_id);
    }
    return { cohorts: [...co].sort(), rooms: [...rm].sort(), lecturers: [...le].sort() };
  }, [sessions, placements]);

  const shownPlacements = useMemo(
    () => (placements ? filterPlacements(placements, sessions, filter) : {}),
    [placements, sessions, filter],
  );

  const shownWalls = useMemo(() => filterWalls(walls, filter), [walls, filter]);

  const filtered = filterCount(filter) > 0;

  // Hebrew course names (ground-truth) for the block labels, keyed by number.
  const courseNames = useMemo(
    () => Object.fromEntries(courses.map((c) => [c.number, c.name_he || c.name_en || ""])),
    [courses],
  );

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
        {terms && (
          <div className="term-picker">
            <select value={terms.current} onChange={(e) => switchTerm(e.target.value)}
              title={t("term", lang)}>
              {terms.terms.map((tm) => (
                <option key={tm.id} value={tm.id}
                  title={tm.published ? t("published", lang) : undefined}>
                  {termLabel(tm.id, lang)}{tm.published ? " ✓" : ""}
                </option>
              ))}
              <option value="__new__">{t("newTerm", lang)}</option>
            </select>
            <button className="ghost" onClick={renameCurrentTerm}
              title={t("renameTermHint", lang)}>✎</button>
          </div>
        )}
        <button className="ghost danger" onClick={resetAll} title={t("resetHint", lang)}>
          ⟲ {t("reset", lang)}
        </button>
        <button className="ghost" onClick={() => setLang(lang === "he" ? "en" : "he")}>
          {lang === "he" ? "EN" : "עב"}
        </button>
      </header>

      {error && <div className="error">{error}</div>}
      {publishDrift && <div className="error">{publishDrift}</div>}
      {notice && <div className="notice">{notice}</div>}
      {/* Only for the open term: the Rename button below acts on that one. */}
      {terms?.needs_naming && terms.needs_naming === terms.current && (
        <div className="notice">
          {t("confirmTermName", lang, { term: termLabel(terms.needs_naming, lang) })}{" "}
          <button className="ghost" onClick={renameCurrentTerm}>{t("renameTerm", lang)}</button>
        </div>
      )}

      {tab === "catalog" && (
        <div className="panel">
          <CatalogPanel
            courses={courses} lang={lang}
            onAdd={(c) => api.upsertCourse(c).then(refresh).catch((e) => setError(String(e)))}
            onDelete={(n) => api.deleteCourse(n).then(refresh)}
            onSeed={() => api.seedCatalog().then(refresh).catch((e) => setError(String(e)))}
            onImport={(f) => api.importCatalog(f).then(refresh).catch((e) => setError(String(e)))}
          />
        </div>
      )}

      {tab === "people" && <div className="panel"><PeoplePanel lang={lang} /></div>}

      {tab === "availability" && (
        <div className="panel"><AvailabilityPanel courses={courses} lang={lang} /></div>
      )}

      {tab === "calendar" && <div className="panel"><CalendarPanel lang={lang} /></div>}

      {tab === "import" && <div className="panel"><ImportPanel lang={lang} /></div>}

      {tab === "checklist" && <div className="panel"><ChecklistPanel lang={lang} /></div>}

      {tab === "schedules" && (
        <div className="panel">
          <SchedulesPanel
            lang={lang} canSave={placements != null}
            onLoaded={(r) => { applyResult(r); setTab("schedule"); }}
          />
        </div>
      )}

      {tab === "schedule" && (
        <div className="panel">
          <div className="toolbar">
            <button className="primary" disabled={solving} onClick={solve}>
              {solving ? t("solving", lang) : t("solve", lang)}
            </button>
            {currentTerm && (currentTerm.published
              ? (
                <button className="ghost" onClick={unpublishTerm}
                  title={`${t("published", lang)} ${currentTerm.published}`}>
                  🔒 {t("unpublish", lang)}
                </button>
              )
              : (
                <button className="ghost" disabled={!placements} onClick={publishTerm}
                  title={t("publishHint", lang)}>
                  🔒 {t("publish", lang)}
                </button>
              ))}
            {placements && (
              <>
                <div className="seg" role="group">
                  <button className={layout === "grid" ? "seg-btn active" : "seg-btn"}
                    onClick={() => setLayout("grid")}>{t("layoutGrid", lang)}</button>
                  <button className={layout === "rooms" ? "seg-btn active" : "seg-btn"}
                    onClick={() => setLayout("rooms")}>{t("layoutRooms", lang)}</button>
                </div>
                <div className="seg" role="group">
                  <button className="seg-btn" disabled={!canUndo} onClick={undo}
                    title={`${t("undo", lang)} (Ctrl+Z)`}>↶ {t("undo", lang)}</button>
                  <button className="seg-btn" disabled={!canRedo} onClick={redo}
                    title={`${t("redo", lang)} (Ctrl+Y)`}>↷ {t("redo", lang)}</button>
                </div>
                {layout === "grid" && (
                  <div className="filters">
                    <MultiSelect
                      label={t("filterCourses", lang)} allLabel={t("allCourses", lang)}
                      options={COURSE_GROUPS.map((g) => ({
                        value: g, label: g === "other" ? t("otherDept", lang) : `${g}…`,
                      }))}
                      selected={filter.groups}
                      onChange={(groups) => setFilter({ ...filter, groups })}
                    />
                    <MultiSelect
                      label={t("filterAudience", lang)} allLabel={t("allAudiences", lang)}
                      options={[
                        ...cohorts.map((c) => ({ value: c, label: c })),
                        { value: GRAD_AUDIENCE, label: t("gradCourses", lang) },
                      ]}
                      selected={filter.audience}
                      onChange={(audience) => setFilter({ ...filter, audience })}
                    />
                    <MultiSelect
                      label={t("byRoom", lang)} allLabel={t("allRooms", lang)}
                      options={rooms.map((r) => ({ value: r, label: ROOM_NAME[r] ?? r }))}
                      selected={filter.rooms}
                      onChange={(rms) => setFilter({ ...filter, rooms: rms })}
                    />
                    <MultiSelect
                      label={t("byLecturer", lang)} allLabel={t("allLecturers", lang)}
                      options={lecturers.map((l) => ({ value: l, label: l }))}
                      selected={filter.lecturers}
                      onChange={(lect) => setFilter({ ...filter, lecturers: lect })}
                    />
                    {filtered && (
                      <button className="ghost" onClick={() => setFilter(NO_FILTER)}>
                        ✕ {t("clearFilters", lang)}
                      </button>
                    )}
                  </div>
                )}
                <div className="spacer" />
                {layout === "grid" && filtered && (
                  <span className="badge count" title={t("shownOfTotal", lang)}>
                    {Object.keys(shownPlacements).length}/{Object.keys(placements).length}
                  </span>
                )}
                {parked.length > 0 && (
                  <button className="badge warn" title={t("unplacedHint", lang)}
                    onClick={() => setLayout("rooms")}>
                    {parked.length} {t("unplaced", lang)}
                  </button>
                )}
                <span className={hardCount ? "badge bad" : "badge ok"}>
                  {hardCount ? `${hardCount} ⚠` : t("feasible", lang)}
                </span>
                <button className="ghost" onClick={saveCurrent} title={t("saveSchedule", lang)}>
                  💾 {saveMsg ?? t("save", lang)}
                </button>
                <a className="ghost" href={api.exportCsvUrl()} download>Excel</a>
                <a className="ghost" href={api.exportPdfUrl("cohort")} target="_blank" rel="noopener">{t("pdfGrid", lang)}</a>
                <a className="ghost" href={api.exportPdfUrl("flat")} target="_blank" rel="noopener">{t("pdfList", lang)}</a>
              </>
            )}
          </div>

          {placements ? (
            <div className="schedule-body">
              <div className="grid-wrap">
                {layout === "rooms" ? (
                  <RoomBoards
                    placements={placements} sessions={sessions} violations={violations}
                    walls={walls} parked={parked} lang={lang} selectedId={selected} names={courseNames}
                    onMove={onMove} onPark={onPark} onSelect={setSelected}
                    validateDrop={validateDrop}
                  />
                ) : (
                  <WeeklyGrid
                    placements={shownPlacements} sessions={sessions} violations={violations}
                    walls={shownWalls} lang={lang} selectedId={selected} names={courseNames}
                    onMove={onMove} onSelect={setSelected}
                    validateDrop={validateDrop}
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
                            {m?.fixed && <span title={t("fixedTag", lang)}> ⚓</span>}
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
