import { useRef, useState } from "react";
import { api } from "../api";
import type { OfferedRow } from "../types";
import { DAY_NAMES, minutesToHHMM, t, type Lang } from "../i18n";

// Skeleton import + review: upload the Technion XLSX, the backend parses and
// filters it to the catalog's courses, and the parsed sessions are shown for the
// planner to review before solving.
export function ImportPanel({ lang }: { lang: Lang }) {
  const [rows, setRows] = useState<OfferedRow[] | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  const onFile = async (f: File) => {
    setBusy(true);
    setError(null);
    try {
      const r = await api.uploadSkeleton(f);
      setRows(r.offered);
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  };

  const dayName = (d: number | null) => (d == null || d > 4 ? "—" : DAY_NAMES[lang][d]);
  const timeRange = (r: OfferedRow) =>
    r.start_min == null ? "—" : `${minutesToHHMM(r.start_min)}–${minutesToHHMM(r.end_min)}`;

  return (
    <div className="import">
      <h2>{t("importSkeleton", lang)}</h2>
      <p className="muted">{t("importHint", lang)}</p>
      <div className="upload">
        <input
          ref={fileRef} type="file" accept=".xlsx,.xls" hidden
          onChange={(e) => e.target.files?.[0] && onFile(e.target.files[0])}
        />
        <button className="primary" disabled={busy} onClick={() => fileRef.current?.click()}>
          {busy ? t("importing", lang) : t("importSkeleton", lang)}
        </button>
      </div>

      {error && <div className="error">{error}</div>}

      {rows == null ? (
        <p className="empty">{t("noOffered", lang)}</p>
      ) : (
        <>
          <h3>{t("offeredSessions", lang)} ({rows.length})</h3>
          <table className="data">
            <thead>
              <tr>
                <th>{t("number", lang)}</th>
                <th>{t("type", lang)}</th>
                <th>{t("group", lang)}</th>
                <th>{t("day", lang)}</th>
                <th>{t("time", lang)}</th>
                <th>{t("room", lang)}</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r, i) => (
                <tr key={i}>
                  <td>{r.course_number}</td>
                  <td>{r.event_type ?? "—"}</td>
                  <td>{r.group_code ?? "—"}</td>
                  <td>{dayName(r.day)}</td>
                  <td>{timeRange(r)}</td>
                  <td>{r.room || "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </>
      )}
    </div>
  );
}
