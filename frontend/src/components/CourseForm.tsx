import { useState } from "react";
import type { Course, Program, Role } from "../types";
import { PROGRAMS, ROLES, ROOMS } from "../types";
import {
  DAY_NAMES,
  ROLE_LABEL,
  hhmmToMinutes,
  minutesToHHMM,
  t,
  type Lang,
} from "../i18n";

interface Props {
  initial: Course;
  isNew: boolean;
  lang: Lang;
  onSave: (c: Course) => void;
  onCancel: () => void;
}

// Full course editor — every piece of metadata the solver needs. External
// courses are immovable walls, so they swap the session-structure section for a
// fixed day/time/room placement.
export function CourseForm({ initial, isNew, lang, onSave, onCancel }: Props) {
  const [c, setC] = useState<Course>(initial);
  const set = (patch: Partial<Course>) => setC((prev) => ({ ...prev, ...patch }));

  const toggleProgram = (p: Program) =>
    set({
      programs: c.programs.includes(p)
        ? c.programs.filter((x) => x !== p)
        : [...c.programs, p],
    });

  const toggleLabDay = (d: number) => {
    const days = c.lab_days ?? [];
    set({ lab_days: days.includes(d) ? days.filter((x) => x !== d) : [...days, d] });
  };

  const csv = (s: string) => s.split(",").map((x) => x.trim()).filter(Boolean);

  const valid = c.number.trim() !== "" && c.programs.length > 0;

  return (
    <div className="form">
      <h3>{isNew ? t("newCourse", lang) : t("editCourse", lang)}</h3>

      <label>{t("number", lang)}
        <input value={c.number} disabled={!isNew}
          onChange={(e) => set({ number: e.target.value })} />
      </label>
      <div className="row">
        <label>{t("nameHe", lang)}
          <input value={c.name_he ?? ""} onChange={(e) => set({ name_he: e.target.value })} />
        </label>
        <label>{t("nameEn", lang)}
          <input value={c.name_en ?? ""} onChange={(e) => set({ name_en: e.target.value })} />
        </label>
      </div>

      <fieldset>
        <legend>{t("programs", lang)}</legend>
        {PROGRAMS.map((p) => (
          <label key={p} className="chk">
            <input type="checkbox" checked={c.programs.includes(p)}
              onChange={() => toggleProgram(p)} />
            {p}
          </label>
        ))}
      </fieldset>

      <div className="row">
        <label>{t("year", lang)}
          <select value={c.year} onChange={(e) => set({ year: Number(e.target.value) })}>
            {[1, 2, 3, 4].map((y) => <option key={y} value={y}>{y}</option>)}
          </select>
        </label>
        <label>{t("role", lang)}
          <select value={c.role} onChange={(e) => set({ role: e.target.value as Role })}>
            {ROLES.map((r) => <option key={r} value={r}>{ROLE_LABEL[r][lang]}</option>)}
          </select>
        </label>
        <label>{t("enrollment", lang)}
          <input type="number" min={0} value={c.expected_enrollment ?? 0}
            onChange={(e) => set({ expected_enrollment: Number(e.target.value) })} />
        </label>
      </div>

      <label className="chk">
        <input type="checkbox" checked={!!c.is_external}
          onChange={(e) => set({ is_external: e.target.checked })} />
        {t("external", lang)}
      </label>

      {c.is_external ? (
        <fieldset>
          <legend>{t("placement", lang)}</legend>
          <div className="row">
            <label>{DAY_NAMES[lang][0] /* label only */ && t("from", lang)}
              <select value={c.ext_day ?? 0}
                onChange={(e) => set({ ext_day: Number(e.target.value) })}>
                {DAY_NAMES[lang].map((d, i) => <option key={i} value={i}>{d}</option>)}
              </select>
            </label>
            <label>{t("from", lang)}
              <input type="time" value={minutesToHHMM(c.ext_start_min)}
                onChange={(e) => set({ ext_start_min: hhmmToMinutes(e.target.value) })} />
            </label>
            <label>{t("to", lang)}
              <input type="time" value={minutesToHHMM(c.ext_end_min)}
                onChange={(e) => set({ ext_end_min: hhmmToMinutes(e.target.value) })} />
            </label>
            <label>{t("room", lang)}
              <select value={c.ext_room ?? ""}
                onChange={(e) => set({ ext_room: e.target.value || null })}>
                <option value="">—</option>
                {ROOMS.map((r) => <option key={r.id} value={r.id}>{r.name}</option>)}
              </select>
            </label>
          </div>
        </fieldset>
      ) : (
        <fieldset>
          <legend>{t("sessions", lang)}</legend>
          <div className="row">
            <label>{t("lectureHours", lang)}
              <input type="number" min={0} value={c.lecture_boxes ?? 0}
                onChange={(e) => set({ lecture_boxes: Number(e.target.value) })} />
            </label>
            <label>{t("exerciseGroups", lang)}
              <input type="number" min={0} value={c.num_exercise_groups ?? 0}
                onChange={(e) => set({ num_exercise_groups: Number(e.target.value) })} />
            </label>
            <label>{t("exerciseHours", lang)}
              <input type="number" min={0} value={c.exercise_boxes ?? 1}
                onChange={(e) => set({ exercise_boxes: Number(e.target.value) })} />
            </label>
            <label>{t("labHours", lang)}
              <input type="number" min={0} value={c.lab_boxes ?? 0}
                onChange={(e) => set({ lab_boxes: Number(e.target.value) })} />
            </label>
          </div>
          {(c.lab_boxes ?? 0) > 0 && (
            <div className="lab-days">
              <span>{t("labDays", lang)}:</span>
              {DAY_NAMES[lang].map((d, i) => (
                <label key={i} className="chk">
                  <input type="checkbox" checked={(c.lab_days ?? []).includes(i)}
                    onChange={() => toggleLabDay(i)} />
                  {d}
                </label>
              ))}
            </div>
          )}
          <div className="row">
            <label className="chk">
              <input type="checkbox" checked={!!c.needs_computer_farm}
                onChange={(e) => set({ needs_computer_farm: e.target.checked })} />
              {t("computerFarm", lang)}
            </label>
            <label className="chk">
              <input type="checkbox" checked={!!c.is_remote}
                onChange={(e) => set({ is_remote: e.target.checked })} />
              {t("remote", lang)}
            </label>
          </div>
          <label>{t("lecturers", lang)}
            <input value={(c.lecturer_ids ?? []).join(", ")}
              onChange={(e) => set({ lecturer_ids: csv(e.target.value) })} />
          </label>
          <label>{t("tas", lang)}
            <input value={(c.ta_ids ?? []).join(", ")}
              onChange={(e) => set({ ta_ids: csv(e.target.value) })} />
          </label>
        </fieldset>
      )}

      {!valid && <p className="hint">{t("required", lang)}</p>}
      <div className="form-actions">
        <button className="primary" disabled={!valid} onClick={() => onSave(c)}>
          {t("save", lang)}
        </button>
        <button onClick={onCancel}>{t("cancel", lang)}</button>
      </div>
    </div>
  );
}

export function blankCourse(): Course {
  return {
    number: "", programs: ["ChemE"], year: 2, role: "core",
    lecture_boxes: 2, num_exercise_groups: 1, exercise_boxes: 1, lab_boxes: 0,
    lab_days: [], expected_enrollment: 40, lecturer_ids: [], ta_ids: [],
  };
}
