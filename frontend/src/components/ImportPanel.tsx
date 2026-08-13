import { Fragment, useEffect, useRef, useState } from "react";
import { api } from "../api";
import type { OfferedRow } from "../types";
import {
  DAY_NAMES, detailLabel, hhmmToMinutes, minutesToHHMM, t, type Lang,
} from "../i18n";

// Client mirror of the backend `pinnable` rule: a row pins iff it has a weekday
// (0..4) and a grid-aligned start (08:30 + whole hours, within the day).
function isPinnable(r: OfferedRow): boolean {
  if (r.day == null || r.day < 0 || r.day > 4 || r.start_min == null) return false;
  const off = r.start_min - (8 * 60 + 30);
  return off >= 0 && off % 60 === 0 && off / 60 < 10;
}

// The pass-through skeleton columns worth showing beside the `details` bag —
// these three are first-class fields on the row, not detail entries.
const NAMED_DETAILS: Array<[keyof OfferedRow, string]> = [
  ["person", "person"],
  ["faculty", "faculty"],
  ["language", "language"],
];

// Skeleton import + review/correct: upload the Technion export — .xlsx or .xlsm,
// the zip-based formats openpyxl reads — and the backend parses it and keeps only
// our courses of interest. Then hand-edit the parsed rows —
// day, start time, group — before they drive the solve. Rows with a grid-aligned
// day+time are anchored (⚓) for the solver (option a). Save persists to the
// backend; the next Solve uses the corrected rows.
//
// Each row can be expanded to show its whole record: every named column of the
// export the parser carried through, rendered from `details` so a column added
// upstream needs no change here.
export function ImportPanel({ lang }: { lang: Lang }) {
  const [rows, setRows] = useState<OfferedRow[] | null>(null);
  const [busy, setBusy] = useState(false);
  const [saving, setSaving] = useState(false);
  const [dirty, setDirty] = useState(false);
  const [dragOver, setDragOver] = useState(false);
  const [needsCoi, setNeedsCoi] = useState(false);
  const [open, setOpen] = useState<Set<number>>(new Set());
  const [error, setError] = useState<string | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  // Keyed by the row's source-spreadsheet number, not its array index: deleting
  // a row shifts every index below it, which would silently move the expansion
  // onto a different row. A stale id here simply matches nothing.
  const toggle = (rowId: number) =>
    setOpen((prev) => {
      const next = new Set(prev);
      next.has(rowId) ? next.delete(rowId) : next.add(rowId);
      return next;
    });

  useEffect(() => {
    api.getSkeletonRows()
      .then((r) => { if (r.length) setRows(r); })
      .catch((e) => setError(String(e)));
  }, []);

  const onFile = async (f: File) => {
    // Not /\.xlsx?$/ — that also admits legacy .xls, which openpyxl can't read.
    // A .xls is called out by name: it looks supported, so "needs an Excel file"
    // would read as a contradiction rather than an instruction.
    if (!/\.xls[xm]$/i.test(f.name)) {
      setError(t(/\.xls$/i.test(f.name) ? "legacyXls" : "needsExcel", lang));
      return;
    }
    setBusy(true);
    setError(null);
    setRows(null); // a new import starts clean — drop the previous data first
    setOpen(new Set());
    try {
      const r = await api.uploadSkeleton(f);
      setRows(r.offered);
      setNeedsCoi(r.warning === "no_courses_of_interest");
      setDirty(false);
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  };

  const onDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(false);
    const f = e.dataTransfer.files?.[0];
    if (f) onFile(f);
  };

  const clearImport = async () => {
    if (!window.confirm(t("clearImportConfirm", lang))) return;
    setError(null);
    try {
      await api.clearSkeletonRows();
      setRows(null);
      setNeedsCoi(false);
      setOpen(new Set());
      setDirty(false);
    } catch (e) {
      setError(String(e));
    }
  };

  const patch = (i: number, p: Partial<OfferedRow>) => {
    setRows((prev) => prev && prev.map((r, j) => (j === i ? { ...r, ...p } : r)));
    setDirty(true);
  };
  const removeRow = (i: number) => {
    setRows((prev) => prev && prev.filter((_, j) => j !== i));
    setDirty(true);
  };

  const setStart = (i: number, hhmm: string, row: OfferedRow) => {
    const start = hhmmToMinutes(hhmm);
    // Preserve the existing duration (default 60 min) when only the start moves.
    const dur = row.start_min != null && row.end_min != null
      ? row.end_min - row.start_min : 60;
    patch(i, { start_min: start, end_min: start == null ? null : start + dur });
  };

  const save = async () => {
    if (!rows) return;
    setSaving(true);
    setError(null);
    try {
      const out = await api.putSkeletonRows(rows);
      setRows(out.offered);
      setDirty(false);
    } catch (e) {
      setError(String(e));
    } finally {
      setSaving(false);
    }
  };

  const pinnedCount = rows?.filter(isPinnable).length ?? 0;

  return (
    <div
      className="import"
      onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
      onDragLeave={() => setDragOver(false)}
      onDrop={onDrop}
    >
      <div className="toolbar">
        <input
          ref={fileRef} type="file" accept=".xlsx,.xlsm" hidden
          onChange={(e) => e.target.files?.[0] && onFile(e.target.files[0])}
        />
        <button className="primary" disabled={busy} onClick={() => fileRef.current?.click()}>
          {busy ? t("importing", lang) : t("importSkeleton", lang)}
        </button>
        <div className="spacer" />
        {rows && (
          <>
            <button className="ghost danger" onClick={clearImport}>{t("clearImport", lang)}</button>
            <button className="ghost" disabled={!dirty || saving} onClick={save}>
              {saving ? t("saving", lang) : t("save", lang)}
            </button>
          </>
        )}
      </div>

      <div
        className={dragOver ? "dropzone over" : "dropzone"}
        onClick={() => fileRef.current?.click()}
      >
        {busy ? t("importing", lang)
          : dragOver ? t("dropToImport", lang)
          : t("dropHere", lang)}
      </div>
      <p className="muted">{t("importHint", lang)} · {t("importReplaceHint", lang)}</p>

      {error && <div className="error">{error}</div>}
      {needsCoi && <div className="check-banner missing">{t("importNeedsCoi", lang)}</div>}

      {rows == null ? (
        <p className="empty">{t("noOffered", lang)}</p>
      ) : (
        <>
          <h3>
            {t("offeredSessions", lang)} ({rows.length}) · ⚓ {pinnedCount}
          </h3>
          <p className="muted">{t("pinnedHint", lang)}</p>
          <table className="data editable">
            <thead>
              <tr>
                <th aria-label={t("showDetails", lang)}></th>
                <th>{t("number", lang)}</th>
                <th>{t("type", lang)}</th>
                <th>{t("group", lang)}</th>
                <th>{t("day", lang)}</th>
                <th>{t("time", lang)}</th>
                <th>{t("room", lang)}</th>
                <th aria-label="anchor">⚓</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r, i) => (
                <Fragment key={r.row}>
                <tr className={isPinnable(r) ? "pinned-row" : ""}>
                  <td>
                    <button className="link" aria-expanded={open.has(r.row)}
                      aria-label={t("showDetails", lang)}
                      title={t("showDetails", lang)} onClick={() => toggle(r.row)}>
                      {open.has(r.row) ? "▾" : "▸"}
                    </button>
                  </td>
                  <td>{r.course_number}</td>
                  <td>{r.event_type ?? "—"}</td>
                  <td>
                    <input className="cell" value={r.group_code ?? ""}
                      onChange={(e) => patch(i, { group_code: e.target.value || null })} />
                  </td>
                  <td>
                    <select className="cell" value={r.day ?? ""}
                      onChange={(e) => patch(i, { day: e.target.value === "" ? null : Number(e.target.value) })}>
                      <option value="">—</option>
                      {DAY_NAMES[lang].map((nm, d) => <option key={d} value={d}>{nm}</option>)}
                    </select>
                  </td>
                  <td>
                    <input className="cell" type="time" step={1800}
                      value={minutesToHHMM(r.start_min)}
                      onChange={(e) => setStart(i, e.target.value, r)} />
                  </td>
                  <td>{r.room || "—"}</td>
                  <td>{isPinnable(r) ? "⚓" : ""}</td>
                  <td>
                    <button className="link" title="delete" onClick={() => removeRow(i)}>✕</button>
                  </td>
                </tr>
                {open.has(r.row) && (
                  <tr className="detail-row">
                    <td colSpan={9}>
                      <div className="row-name">{r.name_he || r.name_en}</div>
                      <dl className="row-details">
                        {NAMED_DETAILS.map(([field, key]) => {
                          const value = r[field];
                          return value ? (
                            <div key={key}>
                              <dt>{detailLabel(key, lang)}</dt>
                              <dd>{String(value)}</dd>
                            </div>
                          ) : null;
                        })}
                        {Object.entries(r.details ?? {}).map(([key, value]) => (
                          <div key={key}>
                            <dt>{detailLabel(key, lang)}</dt>
                            <dd>{value}</dd>
                          </div>
                        ))}
                      </dl>
                    </td>
                  </tr>
                )}
                </Fragment>
              ))}
            </tbody>
          </table>
        </>
      )}
    </div>
  );
}
