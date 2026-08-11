import { useEffect, useMemo, useRef, useState } from "react";
import { api } from "../api";
import type { CourseOfInterest } from "../types";
import { t, type Lang } from "../i18n";

// Courses of interest: the hand-maintained list of course numbers the department
// cares about. It is the filter applied to the university-wide skeleton on
// import, so it is a real input file — loadable, exportable, templated — and the
// table below stays editable for the odd one-off correction.
//
// The panel also verifies each number actually appears in the imported skeleton.
// Missing courses get a bold red alert; otherwise a simple green all-clear.
export function ChecklistPanel({ lang }: { lang: Lang }) {
  const [items, setItems] = useState<CourseOfInterest[]>([]);
  const [skeleton, setSkeleton] = useState<{ imported: boolean; numbers: string[] }>(
    { imported: false, numbers: [] },
  );
  const [dirty, setDirty] = useState(false);
  const [saving, setSaving] = useState(false);
  const [loaded, setLoaded] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    Promise.all([api.getCoursesOfInterest(), api.skeletonCourseNumbers()])
      .then(([coi, sk]) => { setItems(coi); setSkeleton(sk); })
      .catch((e) => setError(String(e)));
  }, []);

  const pickFile = async (f: File | undefined) => {
    if (!f) return;
    if (items.length > 0 && !window.confirm(t("coiImportConfirm", lang))) return;
    setError(null);
    setLoaded(null);
    try {
      const next = await api.importCoursesOfInterest(f);
      setItems(next);
      setLoaded(next.length);
      setDirty(false);
    } catch (e) { setError(String(e)); }
  };

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
      {loaded !== null && (
        <div className="check-banner ok">
          {t("coiLoaded", lang).replace("{n}", String(loaded))}
        </div>
      )}

      {banner}

      <div className="toolbar">
        <input ref={fileRef} type="file" accept=".csv,.xlsx,.xlsm" hidden
          onChange={(e) => { pickFile(e.target.files?.[0]); e.target.value = ""; }} />
        <button className="primary" onClick={() => fileRef.current?.click()}>
          {t("coiImport", lang)}
        </button>
        <a className="ghost" href={api.coiTemplateUrl()} download>
          {t("coiTemplate", lang)}
        </a>
        {items.length > 0 && (
          <a className="ghost" href={api.coiExportUrl()} download>
            {t("coiExport", lang)}
          </a>
        )}
        <button className="ghost" onClick={addRow}>＋ {t("addNumber", lang)}</button>
        <div className="spacer" />
        <button className="primary" disabled={!dirty || saving} onClick={save}>
          {saving ? t("saving", lang) : t("save", lang)}
        </button>
      </div>
      <p className="muted">{t("coiFileHint", lang)}</p>

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
