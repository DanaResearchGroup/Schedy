import { useEffect, useRef, useState } from "react";
import { api } from "../api";
import type { OfferedRow } from "../types";
import { DAY_NAMES, hhmmToMinutes, minutesToHHMM, t, type Lang } from "../i18n";

// Client mirror of the backend `pinnable` rule: a row pins iff it has a weekday
// (0..4) and a grid-aligned start (08:30 + whole hours, within the day).
function isPinnable(r: OfferedRow): boolean {
  if (r.day == null || r.day < 0 || r.day > 4 || r.start_min == null) return false;
  const off = r.start_min - (8 * 60 + 30);
  return off >= 0 && off % 60 === 0 && off / 60 < 10;
}

// Skeleton import + review/correct: upload the Technion XLSX (the backend parses
// and filters it to the catalog), then hand-edit the parsed rows — day, start
// time, group — before they drive the solve. Rows with a grid-aligned day+time
// are pinned (🔒) as hard fixed placements (option a). Save persists to the
// backend; the next Solve uses the corrected rows.
export function ImportPanel({ lang }: { lang: Lang }) {
  const [rows, setRows] = useState<OfferedRow[] | null>(null);
  const [busy, setBusy] = useState(false);
  const [saving, setSaving] = useState(false);
  const [dirty, setDirty] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    api.getSkeletonRows()
      .then((r) => { if (r.length) setRows(r); })
      .catch((e) => setError(String(e)));
  }, []);

  const onFile = async (f: File) => {
    setBusy(true);
    setError(null);
    try {
      const r = await api.uploadSkeleton(f);
      setRows(r.offered);
      setDirty(false);
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
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
    <div className="import">
      <div className="toolbar">
        <input
          ref={fileRef} type="file" accept=".xlsx,.xls" hidden
          onChange={(e) => e.target.files?.[0] && onFile(e.target.files[0])}
        />
        <button className="primary" disabled={busy} onClick={() => fileRef.current?.click()}>
          {busy ? t("importing", lang) : t("importSkeleton", lang)}
        </button>
        <div className="spacer" />
        {rows && (
          <button className="ghost" disabled={!dirty || saving} onClick={save}>
            {saving ? t("saving", lang) : t("save", lang)}
          </button>
        )}
      </div>
      <p className="muted">{t("importHint", lang)}</p>

      {error && <div className="error">{error}</div>}

      {rows == null ? (
        <p className="empty">{t("noOffered", lang)}</p>
      ) : (
        <>
          <h3>
            {t("offeredSessions", lang)} ({rows.length}) · 🔒 {pinnedCount}
          </h3>
          <p className="muted">{t("pinnedHint", lang)}</p>
          <table className="data editable">
            <thead>
              <tr>
                <th>{t("number", lang)}</th>
                <th>{t("type", lang)}</th>
                <th>{t("group", lang)}</th>
                <th>{t("day", lang)}</th>
                <th>{t("time", lang)}</th>
                <th>{t("room", lang)}</th>
                <th aria-label="pinned">🔒</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r, i) => (
                <tr key={i} className={isPinnable(r) ? "pinned-row" : ""}>
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
                  <td>{isPinnable(r) ? "🔒" : ""}</td>
                  <td>
                    <button className="link" title="delete" onClick={() => removeRow(i)}>✕</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </>
      )}
    </div>
  );
}
