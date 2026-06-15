import { useEffect, useMemo, useState } from "react";
import { api } from "../api";
import type { CourseOfInterest } from "../types";
import { t, type Lang } from "../i18n";

// Courses-of-interest check: the planner lists the course numbers we care about
// (editable each term) and we verify each one appears in the imported, full
// university-wide skeleton. Missing courses get a bold red alert; otherwise a
// simple green all-clear.
export function ChecklistPanel({ lang }: { lang: Lang }) {
  const [items, setItems] = useState<CourseOfInterest[]>([]);
  const [skeleton, setSkeleton] = useState<{ imported: boolean; numbers: string[] }>(
    { imported: false, numbers: [] },
  );
  const [dirty, setDirty] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([api.getCoursesOfInterest(), api.skeletonCourseNumbers()])
      .then(([coi, sk]) => { setItems(coi); setSkeleton(sk); })
      .catch((e) => setError(String(e)));
  }, []);

  const present = useMemo(() => new Set(skeleton.numbers), [skeleton.numbers]);
  const missing = items.filter((it) => it.number && !present.has(it.number));

  const setRow = (i: number, p: Partial<CourseOfInterest>) => {
    setItems((prev) => prev.map((r, j) => (j === i ? { ...r, ...p } : r)));
    setDirty(true);
  };
  const addRow = () => { setItems((p) => [...p, { number: "", name: "" }]); setDirty(true); };
  const removeRow = (i: number) => { setItems((p) => p.filter((_, j) => j !== i)); setDirty(true); };

  const save = async () => {
    setSaving(true); setError(null);
    try {
      setItems(await api.setCoursesOfInterest(items));
      setDirty(false);
    } catch (e) { setError(String(e)); } finally { setSaving(false); }
  };

  const filled = items.filter((it) => it.number.trim());
  const banner = !skeleton.imported ? (
    <div className="check-banner neutral">{t("checkImportFirst", lang)}</div>
  ) : filled.length === 0 ? (
    <div className="check-banner neutral">{t("checkEmpty", lang)}</div>
  ) : missing.length > 0 ? (
    <div className="check-banner missing">
      <strong>⚠ {t("checkMissing", lang)}</strong>
      <div className="missing-nums">{missing.map((m) => m.number).join(", ")}</div>
    </div>
  ) : (
    <div className="check-banner ok"><strong>{t("checkAllAvailable", lang)}</strong></div>
  );

  return (
    <div className="checklist-panel">
      <p className="muted">{t("coiHint", lang)}</p>
      {error && <div className="error">{error}</div>}

      {banner}

      <div className="toolbar">
        <button className="ghost" onClick={addRow}>＋ {t("addNumber", lang)}</button>
        <div className="spacer" />
        <button className="primary" disabled={!dirty || saving} onClick={save}>
          {saving ? t("saving", lang) : t("save", lang)}
        </button>
      </div>

      <table className="data editable coi-table">
        <thead>
          <tr>
            <th>{t("number", lang)}</th>
            <th>{t("nameHe", lang)}</th>
            <th>{skeleton.imported ? "" : ""}</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          {items.map((it, i) => {
            const ok = it.number.trim() && present.has(it.number.trim());
            return (
              <tr key={i} className={skeleton.imported && it.number.trim() ? (ok ? "coi-ok" : "coi-bad") : ""}>
                <td>
                  <input className="cell" value={it.number}
                    onChange={(e) => setRow(i, { number: e.target.value.trim() })}
                    placeholder={t("number", lang)} />
                </td>
                <td>
                  <input className="cell" value={it.name}
                    onChange={(e) => setRow(i, { name: e.target.value })} />
                </td>
                <td className="coi-status">
                  {skeleton.imported && it.number.trim()
                    ? (ok ? <span className="ok">✓ {t("present", lang)}</span>
                          : <span className="bad">✗ {t("missing", lang)}</span>)
                    : ""}
                </td>
                <td>
                  <button className="link" title="delete" onClick={() => removeRow(i)}>✕</button>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
