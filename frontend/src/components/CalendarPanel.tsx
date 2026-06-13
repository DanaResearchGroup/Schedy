import { useEffect, useState } from "react";
import { api } from "../api";
import type { CalendarAnalysis, SemesterCalendar } from "../types";
import { DAY_NAMES, t, type Lang } from "../i18n";

interface Sub { date: string; template: number }

// Semester calendar editor: overlays the dated semester on the abstract weekly
// template. The planner enters the start/end dates, blocked (no-teaching) dates,
// and day-substitutions (a real date that runs a different weekday's template).
// "Analyze" persists the calendar (PUT /calendar) and realizes it (GET
// /calendar/analyze): teaching-day counts per weekday plus, against the last
// solved schedule, uneven sessions and lecture-before-exercise inversions.
export function CalendarPanel({ lang }: { lang: Lang }) {
  const [start, setStart] = useState("");
  const [end, setEnd] = useState("");
  const [blocked, setBlocked] = useState<string[]>([]);
  const [subs, setSubs] = useState<Sub[]>([]);
  const [newBlocked, setNewBlocked] = useState("");
  const [analysis, setAnalysis] = useState<CalendarAnalysis | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.getCalendar()
      .then((c) => {
        if (c.start) setStart(c.start);
        if (c.end) setEnd(c.end);
        setBlocked((c.blocked_dates ?? []).slice().sort());
        setSubs(Object.entries(c.substitutions ?? {})
          .map(([date, template]) => ({ date, template }))
          .sort((a, b) => a.date.localeCompare(b.date)));
      })
      .catch((e) => setError(String(e)));
  }, []);

  const addBlocked = () => {
    if (newBlocked && !blocked.includes(newBlocked)) {
      setBlocked([...blocked, newBlocked].sort());
    }
    setNewBlocked("");
  };
  const removeBlocked = (d: string) => setBlocked(blocked.filter((x) => x !== d));

  const addSub = () => setSubs([...subs, { date: "", template: 0 }]);
  const setSub = (i: number, patch: Partial<Sub>) =>
    setSubs(subs.map((s, j) => (j === i ? { ...s, ...patch } : s)));
  const removeSub = (i: number) => setSubs(subs.filter((_, j) => j !== i));

  const build = (): SemesterCalendar => ({
    start,
    end,
    blocked_dates: blocked,
    substitutions: Object.fromEntries(
      subs.filter((s) => s.date).map((s) => [s.date, s.template]),
    ),
  });

  // Analyze always persists the on-screen calendar first, so results match it.
  const analyze = async () => {
    setBusy(true);
    setError(null);
    try {
      await api.setCalendar(build());
      setAnalysis(await api.analyzeCalendar());
    } catch (e) {
      setError(String(e));
      setAnalysis(null);
    } finally {
      setBusy(false);
    }
  };

  const dayName = (t0: number | null) => (t0 == null ? "—" : DAY_NAMES[lang][t0]);
  const ready = Boolean(start && end);

  return (
    <div className="calendar-panel">
      <h2>{t("tabCalendar", lang)}</h2>
      <p className="muted">{t("calendarHint", lang)}</p>
      {error && <div className="error">{error}</div>}

      <div className="cal-form">
        <label>
          {t("semesterStart", lang)}
          <input type="date" value={start} onChange={(e) => setStart(e.target.value)} />
        </label>
        <label>
          {t("semesterEnd", lang)}
          <input type="date" value={end} onChange={(e) => setEnd(e.target.value)} />
        </label>
      </div>

      <fieldset className="cal-section">
        <legend>{t("blockedDates", lang)}</legend>
        <div className="cal-add">
          <input type="date" value={newBlocked} onChange={(e) => setNewBlocked(e.target.value)} />
          <button className="ghost" onClick={addBlocked} disabled={!newBlocked}>
            {t("addItem", lang)}
          </button>
        </div>
        <div className="chips">
          {blocked.map((d) => (
            <span key={d} className="chip">
              {d}
              <button className="chip-x" onClick={() => removeBlocked(d)} aria-label="remove">×</button>
            </span>
          ))}
        </div>
      </fieldset>

      <fieldset className="cal-section">
        <legend>{t("substitutions", lang)}</legend>
        {subs.map((s, i) => (
          <div key={i} className="cal-sub">
            <input type="date" value={s.date} onChange={(e) => setSub(i, { date: e.target.value })} />
            <span className="muted">{t("runsAs", lang)}</span>
            <select value={s.template} onChange={(e) => setSub(i, { template: Number(e.target.value) })}>
              {DAY_NAMES[lang].map((nm, d) => <option key={d} value={d}>{nm}</option>)}
            </select>
            <button className="chip-x" onClick={() => removeSub(i)} aria-label="remove">×</button>
          </div>
        ))}
        <button className="ghost" onClick={addSub}>+ {t("addItem", lang)}</button>
      </fieldset>

      <div className="toolbar">
        <button className="primary" onClick={analyze} disabled={!ready || busy}>
          {busy ? t("analyzing", lang) : t("analyze", lang)}
        </button>
      </div>

      {analysis && (
        <section className="cal-analysis">
          <div className="stats">
            <span className="stat"><b>{analysis.teaching_days}</b> {t("teachingDaysLabel", lang)}</span>
            <span className="stat"><b>{analysis.weeks}</b> {t("weeksLabel", lang)}</span>
            <span className="stat"><b>{analysis.blocked_count}</b> {t("blockedLabel", lang)}</span>
          </div>

          <h3>{t("perWeekday", lang)}</h3>
          <table className="data weekday-counts">
            <thead>
              <tr>{DAY_NAMES[lang].map((nm, d) => <th key={d}>{nm}</th>)}</tr>
            </thead>
            <tbody>
              <tr>
                {DAY_NAMES[lang].map((_, d) => (
                  <td key={d}>{analysis.template_counts[String(d)] ?? 0}</td>
                ))}
              </tr>
            </tbody>
          </table>

          <h3>{t("lostSessions", lang)} ({analysis.lost_sessions.length})</h3>
          {analysis.lost_sessions.length === 0 ? (
            <p className="muted">
              {analysis.order_inversions.length === 0 ? t("solveForDeficits", lang) : t("noIssues", lang)}
            </p>
          ) : (
            <ul className="cal-issues">
              {analysis.lost_sessions.map((l) => (
                <li key={l.session_id} className="warn">
                  <span className="kind">{l.course_number}</span> {dayName(l.weekday_template)} ·
                  {" "}{l.realized}/{l.baseline} · {t("deficitLabel", lang)} {l.deficit}
                </li>
              ))}
            </ul>
          )}

          <h3>{t("orderInversions", lang)} ({analysis.order_inversions.length})</h3>
          {analysis.order_inversions.length === 0 ? (
            <p className="muted ok-text">✓ {t("noIssues", lang)}</p>
          ) : (
            <ul className="cal-issues">
              {analysis.order_inversions.map((o, i) => (
                <li key={i} className="warn">
                  <span className="kind">{o.course_number}</span> · {t("weekLabel", lang)} {o.week_index + 1}
                  {o.exercise_group ? ` (${o.exercise_group})` : ""} ·
                  {" "}{o.exercise_date} &lt; {o.lecture_date}
                </li>
              ))}
            </ul>
          )}
        </section>
      )}
    </div>
  );
}
