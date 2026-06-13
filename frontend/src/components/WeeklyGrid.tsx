import type { FixedEvent, Placement, SessionMeta, Violation } from "../types";
import { ROOMS } from "../types";
import { DAY_NAMES, boxLabel, t, type Lang } from "../i18n";

const BOXES = 10; // 08:30..18:30
const DAYS = 5; // Sun..Thu
const ROW_H = 46; // px per academic-hour row (keep in sync with table.grid td height)

const ROOM_NAME = Object.fromEntries(ROOMS.map((r) => [r.id, r.name.split(" (")[0]]));
const TYPE_ABBR: Record<string, string> = { lecture: "L", exercise: "T", lab: "Lab" };

interface Props {
  placements: Record<string, Placement>;
  sessions: Record<string, SessionMeta>;
  violations: Violation[];
  walls: FixedEvent[];
  lang: Lang;
  selectedId: string | null;
  onMove: (sessionId: string, day: number, startBox: number) => void;
  onSelect: (sessionId: string) => void;
}

// The centerpiece editable grid. Blocks are readable (course · group · type ·
// room), colored by role, draggable to move (keeping room), and clickable to
// inspect. Hard-conflicted blocks glow red.
export function WeeklyGrid({
  placements, sessions, violations, walls, lang, selectedId, onMove, onSelect,
}: Props) {
  const conflicted = new Set(
    violations.filter((v) => v.severity === "hard").flatMap((v) => v.session_ids),
  );
  const soft = new Set(
    violations.filter((v) => v.severity === "soft").flatMap((v) => v.session_ids),
  );

  const byCell = new Map<string, string[]>();
  for (const [sid, p] of Object.entries(placements)) {
    const key = `${p.day}:${p.start_box}`;
    byCell.set(key, [...(byCell.get(key) ?? []), sid]);
  }

  const wallsByCell = new Map<string, FixedEvent[]>();
  for (const w of walls) {
    const key = `${w.day}:${w.start_box}`;
    wallsByCell.set(key, [...(wallsByCell.get(key) ?? []), w]);
  }

  const onDrop = (day: number, box: number) => (e: React.DragEvent) => {
    e.preventDefault();
    const sid = e.dataTransfer.getData("text/session");
    if (sid) onMove(sid, day, box);
  };

  return (
    <table className="grid">
      <thead>
        <tr>
          <th className="time-col"></th>
          {Array.from({ length: DAYS }, (_, d) => <th key={d}>{DAY_NAMES[lang][d]}</th>)}
        </tr>
      </thead>
      <tbody>
        {Array.from({ length: BOXES }, (_, box) => (
          <tr key={box}>
            <td className="time-col">{boxLabel(box)}</td>
            {Array.from({ length: DAYS }, (_, day) => {
              const sids = byCell.get(`${day}:${box}`) ?? [];
              const cellWalls = wallsByCell.get(`${day}:${box}`) ?? [];
              return (
                <td key={day} onDragOver={(e) => e.preventDefault()} onDrop={onDrop(day, box)}>
                  {cellWalls.map((w) => (
                    <div
                      key={w.id} className={`wall wall-${w.kind}`}
                      style={{ height: Math.max(1, w.length_boxes) * ROW_H - 4 }}
                      title={w.label}
                    >
                      <span className="wall-label">{w.label}</span>
                    </div>
                  ))}
                  {sids.map((sid, i) => {
                    const m = sessions[sid];
                    const role = m?.role ?? "core";
                    const span = Math.max(1, m?.length_boxes ?? 1);
                    const fixed = m?.fixed ?? false;
                    const cls = [
                      "block", `role-${role}`, fixed ? "fixed" : "",
                      conflicted.has(sid) ? "conflict" : soft.has(sid) ? "soft" : "",
                      selectedId === sid ? "selected" : "",
                    ].join(" ").trim();
                    // Span this session's hours by absolutely sizing it to its
                    // box length; share the cell width with any siblings.
                    const style = {
                      height: span * ROW_H - 4,
                      width: `calc(${100 / sids.length}% - 4px)`,
                      insetInlineStart: `calc(${(100 * i) / sids.length}% + 2px)`,
                    } as const;
                    return (
                      <div
                        key={sid} className={cls} draggable={!fixed} style={style}
                        onDragStart={(e) => fixed
                          ? e.preventDefault()
                          : e.dataTransfer.setData("text/session", sid)}
                        onClick={() => onSelect(sid)}
                        title={m ? `${m.course_number} ${m.type}${fixed ? ` · ${t("fixedTag", lang)}` : ""}` : sid}
                      >
                        <div className="b-top">
                          <span className="b-course">{m?.course_number ?? sid}</span>
                          {fixed && <span className="b-lock" title={t("fixedTag", lang)}>🔒</span>}
                          {m?.group && <span className="b-group">{m.group}</span>}
                        </div>
                        <div className="b-sub">
                          <span className="b-type">{m ? TYPE_ABBR[m.type] : ""}</span>
                          <span className="b-room">{ROOM_NAME[placements[sid].room_id] ?? ""}</span>
                          {m?.is_remote && <span className="b-zoom">⚡</span>}
                        </div>
                      </div>
                    );
                  })}
                </td>
              );
            })}
          </tr>
        ))}
      </tbody>
    </table>
  );
}
