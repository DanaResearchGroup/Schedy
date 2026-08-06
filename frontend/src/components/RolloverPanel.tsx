import { useEffect, useState } from "react";
import { api } from "../api";
import type { RolloverCourse } from "../types";
import { t, termLabel, type Lang } from "../i18n";

interface Props {
  lang: Lang;
  onDone: () => void;
  onClose: () => void;
}

// Last year's graduate courses, offered as provisional stand-ins for this term.
// Ticking one creates a placeholder that holds its hours through phase 1, so a
// joint course is genuinely pushed out of them rather than merely discouraged.
export function RolloverPanel({ lang, onDone, onClose }: Props) {
  const [source, setSource] = useState<string>("");
  const [courses, setCourses] = useState<RolloverCourse[] | null>(null);
  const [picked, setPicked] = useState<Set<string>>(new Set());
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.rolloverPreview()
      .then((r) => {
        setSource(r.source);
        setCourses(r.courses);
        // Cadence says which are due; the planner still decides.
        setPicked(new Set(r.courses.filter((c) => c.due).map((c) => c.number)));
      })
      .catch((e) => setError(String(e)));
  }, []);

  const toggle = (n: string) =>
    setPicked((prev) => {
      const next = new Set(prev);
      next.has(n) ? next.delete(n) : next.add(n);
      return next;
    });

  const apply = async () => {
    try {
      await api.rolloverApply([...picked]);
      onDone();
    } catch (e) {
      setError(String(e));
    }
  };

  return (
    <div className="form">
      <h3>{t("rolloverTitle", lang, { source: source ? termLabel(source, lang) : "" })}</h3>
      {error && <div className="error">{error}</div>}
      <p className="note">{t("rolloverHint", lang)}</p>

      {courses && courses.length === 0 && (
        <p className="empty">{t("rolloverNone", lang)}</p>
      )}

      {courses?.map((c) => (
        <label key={c.number} className="chk">
          <input type="checkbox" checked={picked.has(c.number)}
            onChange={() => toggle(c.number)} />
          <strong>{c.number}</strong> {c.name_he || c.name_en || ""}
          <span className="muted">
            {" · "}{t("rolloverLastRun", lang, { term: termLabel(c.last_run, lang) })}
            {c.cadence === "biennial" ? ` · ${t("cadenceBiennial", lang)}` : ""}
          </span>
        </label>
      ))}

      <div className="row">
        <button className="primary" disabled={picked.size === 0} onClick={apply}>
          {t("rolloverAdd", lang)}
        </button>
        <button className="ghost" onClick={onClose}>{t("cancel", lang)}</button>
      </div>
    </div>
  );
}
