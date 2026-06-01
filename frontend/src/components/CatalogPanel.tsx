import { useState } from "react";
import type { Course } from "../types";
import { t, type Lang } from "../i18n";

interface Props {
  courses: Course[];
  lang: Lang;
  onAdd: (c: Course) => void;
  onDelete: (n: string) => void;
}

// A compact catalog editor. A full build would expand this into the per-course
// form described in the PRD (session structure, room needs, externals); this
// scaffold covers the common case of adding a core course with a lecture.
export function CatalogPanel({ courses, lang, onAdd, onDelete }: Props) {
  const [number, setNumber] = useState("");

  const add = () => {
    if (!number.trim()) return;
    onAdd({
      number: number.trim(),
      programs: ["ChemE"],
      year: 2,
      role: "core",
      lecture_boxes: 2,
      num_exercise_groups: 1,
      exercise_boxes: 1,
      expected_enrollment: 40,
    });
    setNumber("");
  };

  return (
    <div className="catalog">
      <h2>{t("catalog", lang)}</h2>
      <div className="add-row">
        <input
          value={number}
          placeholder={t("number", lang)}
          onChange={(e) => setNumber(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && add()}
        />
        <button onClick={add}>{t("addCourse", lang)}</button>
      </div>
      <ul className="course-list">
        {courses.map((c) => (
          <li key={c.number}>
            <span>
              {c.number} · {c.programs.join("/")} Y{c.year} · {c.role}
            </span>
            <button className="link" onClick={() => onDelete(c.number)}>
              ✕
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}
