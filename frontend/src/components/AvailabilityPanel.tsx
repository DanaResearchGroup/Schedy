import { useEffect, useMemo, useState } from "react";
import { api } from "../api";
import type { Availability, Course } from "../types";
import { boxLabel, DAY_NAMES, t, type Lang } from "../i18n";

const BOXES = 10; // 08:30..18:30
const DAYS = 5; // Sun..Thu
const cellKey = (day: number, box: number) => `${day}:${box}`;

// Per-person teaching availability editor. People are the union of lecturer and
// TA ids declared across the catalog. The grid mirrors WeeklyGrid (Sun-Thu x
// academic hours); clicking a cell toggles whether that person is unavailable
// there. Unavailable cells become hard `person_unavailable` walls for the solver
// (PUT /availability), so re-solving afterwards honors them.
export function AvailabilityPanel({ courses, lang }: { courses: Course[]; lang: Lang }) {
  // Internal model: person -> Set of "day:box" cells they CANNOT teach.
  const [blocked, setBlocked] = useState<Record<string, Set<string>>>({});
  const [person, setPerson] = useState<string | null>(null);
  const [dirty, setDirty] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Only staff on courses actually offered this semester constrain the solve —
  // a lecturer whose course is sitting out is never consulted by the solver.
  const teaching = useMemo(() => {
    const s = new Set<string>();
    for (const c of courses) {
      if (c.offered === false) continue;
      (c.lecturer_ids ?? []).forEach((p) => s.add(p));
      (c.ta_ids ?? []).forEach((p) => s.add(p));
    }
    return [...s].sort();
  }, [courses]);

  // Blocks stored for people not teaching this term. The data is deliberately
  // kept — they return next year — and is inert for the solve, but it stays
  // listed here rather than lurking unseen in the database.
  const notTeaching = useMemo(() => {
    const on = new Set(teaching);
    return Object.keys(blocked)
      .filter((p) => !on.has(p) && (blocked[p]?.size ?? 0) > 0)
      .sort();
  }, [teaching, blocked]);

  const people = useMemo(() => [...teaching, ...notTeaching], [teaching, notTeaching]);

  useEffect(() => {
    api.getAvailability()
      .then((a: Availability) => {
        const next: Record<string, Set<string>> = {};
        for (const [p, cells] of Object.entries(a)) {
          next[p] = new Set(cells.map(([d, b]) => cellKey(d, b)));
        }
        setBlocked(next);
      })
      .catch((e) => setError(String(e)));
  }, []);

  // Default the selector to the first person once the catalog loads.
  useEffect(() => {
    if (person == null && people.length > 0) setPerson(people[0]);
  }, [people, person]);

  const current = (person && blocked[person]) || new Set<string>();

  const toggle = (day: number, box: number) => {
    if (!person) return;
    const key = cellKey(day, box);
    setBlocked((prev) => {
      const set = new Set(prev[person] ?? []);
      set.has(key) ? set.delete(key) : set.add(key);
      return { ...prev, [person]: set };
    });
    setDirty(true);
  };

  const clearPerson = () => {
    if (!person) return;
    setBlocked((prev) => ({ ...prev, [person]: new Set() }));
    setDirty(true);
  };

  const save = async () => {
    setSaving(true);
    setError(null);
    try {
      const payload: Availability = {};
      for (const [p, set] of Object.entries(blocked)) {
        if (set.size === 0) continue;
        payload[p] = [...set].map((k) => {
          const [d, b] = k.split(":").map(Number);
          return [d, b] as [number, number];
        });
      }
      await api.setAvailability(payload);
      setDirty(false);
    } catch (e) {
      setError(String(e));
    } finally {
      setSaving(false);
    }
  };

  if (people.length === 0) {
    return (
      <div className="availability">
        <h2>{t("tabAvailability", lang)}</h2>
        <p className="empty">{t("noPeople", lang)}</p>
      </div>
    );
  }

  return (
    <div className="availability">
      <div className="toolbar">
        <label className="view">
          {t("person", lang)}:
          <select value={person ?? ""} onChange={(e) => setPerson(e.target.value)}>
            {teaching.map((p) => {
              const n = blocked[p]?.size ?? 0;
              return <option key={p} value={p}>{p}{n ? ` (${n})` : ""}</option>;
            })}
            {notTeaching.length > 0 && (
              <optgroup label={t("notTeachingGroup", lang)}>
                {notTeaching.map((p) => (
                  <option key={p} value={p}>{p} ({blocked[p]?.size ?? 0})</option>
                ))}
              </optgroup>
            )}
          </select>
        </label>
        <button className="ghost" onClick={clearPerson} disabled={current.size === 0}>
          {t("clearBlocks", lang)}
        </button>
        <div className="spacer" />
        <button className="primary" onClick={save} disabled={!dirty || saving}>
          {saving ? t("saving", lang) : t("save", lang)}
        </button>
      </div>

      <p className="muted">{t("availabilityHint", lang)}</p>
      {person && notTeaching.includes(person) && (
        <p className="muted note-idle">{t("notTeachingNote", lang)}</p>
      )}
      {error && <div className="error">{error}</div>}

      <table className="grid avail-grid">
        <thead>
          <tr>
            <th className="time-col"></th>
            {Array.from({ length: DAYS }, (_, d) => <th key={d}>{DAY_NAMES[lang][d]}</th>)}
          </tr>
        </thead>
        <tbody>
          {Array.from({ length: BOXES }, (_, box) => (
            <tr key={box}>
              <td className="time-col">{boxLabel(box)}</td>
              {Array.from({ length: DAYS }, (_, day) => {
                const off = current.has(cellKey(day, box));
                return (
                  <td
                    key={day}
                    className={off ? "avail-cell blocked" : "avail-cell"}
                    onClick={() => toggle(day, box)}
                    title={off ? t("unavailable", lang) : t("available", lang)}
                  >
                    {off ? "✕" : ""}
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
