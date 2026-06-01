import { useState } from "react";
import type { Course } from "../types";
import { ROLE_LABEL, t, type Lang } from "../i18n";
import { CourseForm, blankCourse } from "./CourseForm";

interface Props {
  courses: Course[];
  lang: Lang;
  onAdd: (c: Course) => void;
  onDelete: (n: string) => void;
}

// Catalog manager: a list of courses with add / edit / delete, backed by the
// full CourseForm. Editing an existing course locks its number (the primary key).
export function CatalogPanel({ courses, lang, onAdd, onDelete }: Props) {
  const [draft, setDraft] = useState<Course | null>(null);
  const [isNew, setIsNew] = useState(false);

  const startNew = () => { setDraft(blankCourse()); setIsNew(true); };
  const startEdit = (c: Course) => { setDraft({ ...c }); setIsNew(false); };
  const close = () => setDraft(null);
  const save = (c: Course) => { onAdd(c); close(); };

  return (
    <div className="catalog">
      <div className="catalog-head">
        <h2>{t("catalog", lang)}</h2>
        {!draft && <button className="primary" onClick={startNew}>{t("addCourse", lang)}</button>}
      </div>

      {draft ? (
        <CourseForm initial={draft} isNew={isNew} lang={lang} onSave={save} onCancel={close} />
      ) : (
        <ul className="course-list">
          {courses.length === 0 && <li className="muted">—</li>}
          {courses.map((c) => (
            <li key={c.number}>
              <button className="course-link" onClick={() => startEdit(c)}>
                <strong>{c.number}</strong>
                <span className="muted">
                  {(lang === "he" ? c.name_he : c.name_en) || ""}
                </span>
                <span className="tags">
                  <span className={`tag role-${c.role}`}>{ROLE_LABEL[c.role][lang]}</span>
                  {c.programs.map((p) => <span key={p} className="tag">{p}</span>)}
                  <span className="tag">Y{c.year}</span>
                  {c.is_external && <span className="tag ext">ext</span>}
                </span>
              </button>
              <button className="link" title="delete" onClick={() => onDelete(c.number)}>✕</button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
