import { useEffect, useState } from "react";
import { api } from "../api";
import type { SavedMeta, SolveResult } from "../types";
import { t, type Lang } from "../i18n";

interface Props {
  lang: Lang;
  canSave: boolean; // a schedule is currently solved/loaded
  onLoaded: (result: SolveResult) => void;
}

function fmtDate(iso: string): string {
  // ISO -> "YYYY-MM-DD HH:MM" without pulling in a date lib.
  if (!iso) return "";
  return iso.replace("T", " ").replace(/(:\d\d)(\+.*|Z)?$/, "$1").slice(0, 16);
}

// The Saved tab: a managed folder of self-contained schedule snapshots. Save the
// current solution under a name, browse saved scenarios with their stats, and
// load one back (replacing the working state). The saves live as one file each
// in a folder the planner can point anywhere (synced folder, network drive).
export function SchedulesPanel({ lang, canSave, onLoaded }: Props) {
  const [saves, setSaves] = useState<SavedMeta[]>([]);
  const [savesDir, setSavesDir] = useState("");
  const [name, setName] = useState("");
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refresh = () =>
    Promise.all([api.listSchedules(), api.getConfig()])
      .then(([list, cfg]) => { setSaves(list); setSavesDir(cfg.saves_dir); })
      .catch((e) => setError(String(e)));

  useEffect(() => { refresh(); }, []);

  const save = async () => {
    if (!name.trim()) return;
    setBusy(true); setError(null);
    try {
      await api.saveSchedule(name.trim(), note.trim() || undefined);
      setName(""); setNote("");
      await refresh();
    } catch (e) { setError(String(e)); } finally { setBusy(false); }
  };

  const load = async (s: SavedMeta) => {
    if (!window.confirm(t("loadConfirm", lang))) return;
    setBusy(true); setError(null);
    try {
      onLoaded(await api.loadSchedule(s.id));
    } catch (e) { setError(String(e)); } finally { setBusy(false); }
  };

  const rename = async (s: SavedMeta) => {
    const next = window.prompt(t("rename", lang), s.name);
    if (next == null || !next.trim() || next.trim() === s.name) return;
    setError(null);
    try { await api.renameSchedule(s.id, next.trim()); await refresh(); }
    catch (e) { setError(String(e)); }
  };

  const remove = async (s: SavedMeta) => {
    if (!window.confirm(t("deleteConfirm", lang))) return;
    setError(null);
    try { await api.deleteSchedule(s.id); await refresh(); }
    catch (e) { setError(String(e)); }
  };

  const changeFolder = async () => {
    const next = window.prompt(t("savesFolder", lang), savesDir);
    if (next == null) return;
    setError(null);
    try {
      const cfg = await api.setSavesDir(next.trim());
      setSavesDir(cfg.saves_dir);
      await refresh();
    } catch (e) { setError(String(e)); }
  };

  return (
    <div className="schedules-panel">
      {error && <div className="error">{error}</div>}

      <section className="saves-folder">
        <label>{t("savesFolder", lang)}</label>
        <div className="folder-row">
          <code className="folder-path" title={savesDir}>{savesDir}</code>
          <button className="ghost" onClick={changeFolder}>{t("change", lang)}</button>
        </div>
        <p className="muted hint">{t("savesFolderHint", lang)}</p>
      </section>

      <section className="save-current">
        <h3>{t("saveAs", lang)}</h3>
        <div className="save-row">
          <input
            value={name} onChange={(e) => setName(e.target.value)}
            placeholder={t("scheduleName", lang)}
            onKeyDown={(e) => e.key === "Enter" && save()}
          />
          <input
            value={note} onChange={(e) => setNote(e.target.value)}
            placeholder={t("noteOptional", lang)}
          />
          <button className="primary" disabled={!canSave || busy || !name.trim()} onClick={save}>
            {t("save", lang)}
          </button>
        </div>
        {!canSave && <p className="muted hint">{t("needSolveToSave", lang)}</p>}
      </section>

      <section className="saves-list">
        <h3>{t("savedSchedules", lang)} ({saves.length})</h3>
        {saves.length === 0 ? (
          <p className="muted">{t("noSaved", lang)}</p>
        ) : (
          <table className="saves-table">
            <tbody>
              {saves.map((s) => (
                <tr key={s.id}>
                  <td className="s-name">
                    {s.name}
                    {s.note && <span className="s-note"> — {s.note}</span>}
                  </td>
                  <td className="s-date muted">{fmtDate(s.created_at)}</td>
                  <td className="s-stats">
                    <span>{s.stats.sessions ?? 0} {t("sessionsShort", lang)}</span>
                    <span className={s.stats.hard ? "bad" : "ok"}>
                      {s.stats.hard ?? 0} {t("hardShort", lang)}
                    </span>
                    <span className="muted">· {Math.round(s.stats.soft_penalty ?? 0)}</span>
                  </td>
                  <td className="s-actions">
                    <button className="primary" disabled={busy} onClick={() => load(s)}>
                      {t("load", lang)}
                    </button>
                    <button className="ghost" onClick={() => rename(s)}>{t("rename", lang)}</button>
                    <button className="ghost danger" onClick={() => remove(s)}>{t("delete", lang)}</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>
    </div>
  );
}
