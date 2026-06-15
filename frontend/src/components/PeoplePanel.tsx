import { useEffect, useState } from "react";
import { api } from "../api";
import type { Person, PersonKind } from "../types";
import { t, type Lang } from "../i18n";

// Faculty registry: define lecturers and TAs as canonical people (name + kind),
// so the same person is spelled one way everywhere and constraints attach to the
// right individual. "Import from courses" seeds it from staff already named on
// the catalog (lecturers -> faculty, TAs -> grad student).
export function PeoplePanel({ lang }: { lang: Lang }) {
  const [people, setPeople] = useState<Person[]>([]);
  const [dirty, setDirty] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.getPeople().then(setPeople).catch((e) => setError(String(e)));
  }, []);

  const setRow = (i: number, p: Partial<Person>) => {
    setPeople((prev) => prev.map((r, j) => (j === i ? { ...r, ...p } : r)));
    setDirty(true);
  };
  const addRow = () => {
    setPeople((p) => [...p, { id: "", name: "", kind: "faculty" }]);
    setDirty(true);
  };
  const removeRow = (i: number) => {
    setPeople((p) => p.filter((_, j) => j !== i));
    setDirty(true);
  };

  const save = async () => {
    setSaving(true); setError(null);
    try { setPeople(await api.setPeople(people)); setDirty(false); }
    catch (e) { setError(String(e)); } finally { setSaving(false); }
  };

  const importFromCourses = async () => {
    setError(null);
    try { setPeople(await api.importPeopleFromCatalog()); setDirty(false); }
    catch (e) { setError(String(e)); }
  };

  return (
    <div className="people-panel">
      <p className="muted">{t("peopleHint", lang)}</p>
      {error && <div className="error">{error}</div>}

      <div className="toolbar">
        <button className="ghost" onClick={addRow}>＋ {t("addPerson", lang)}</button>
        <button className="ghost" onClick={importFromCourses}>⤓ {t("importFromCourses", lang)}</button>
        <div className="spacer" />
        <button className="primary" disabled={!dirty || saving} onClick={save}>
          {saving ? t("saving", lang) : t("save", lang)}
        </button>
      </div>

      {people.length === 0 ? (
        <p className="empty">{t("noPeopleYet", lang)}</p>
      ) : (
        <table className="data editable people-table">
          <thead>
            <tr>
              <th>{t("personName", lang)}</th>
              <th>{t("kindCol", lang)}</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {people.map((p, i) => (
              <tr key={i}>
                <td>
                  <input className="cell" value={p.name}
                    onChange={(e) => setRow(i, { name: e.target.value })}
                    placeholder={t("personName", lang)} />
                </td>
                <td>
                  <select className="cell" value={p.kind}
                    onChange={(e) => setRow(i, { kind: e.target.value as PersonKind })}>
                    <option value="faculty">{t("kindFaculty", lang)}</option>
                    <option value="grad">{t("kindGrad", lang)}</option>
                  </select>
                </td>
                <td>
                  <button className="link" title="delete" onClick={() => removeRow(i)}>✕</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
