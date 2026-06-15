import type { FixedEvent, Placement, SessionMeta, Violation } from "../types";
import { ROOMS } from "../types";
import { DAY_ABBR, boxLabel, t, type Lang } from "../i18n";

const BOXES = 10; // 08:30..18:30
const DAYS = 5; // Sun..Thu
const ROW_H = 34; // px per academic-hour row (keep in sync with .room-grid td height)
const FARM_ID = "room2"; // the computer-farm room

const TYPE_ABBR: Record<string, string> = { lecture: "L", exercise: "T", lab: "Lab" };

interface Props {
  placements: Record<string, Placement>;
  sessions: Record<string, SessionMeta>;
  violations: Violation[];
  walls: FixedEvent[];
  lang: Lang;
  selectedId: string | null;
  onMove: (sessionId: string, day: number, startBox: number, room: string) => void;
  onSelect: (sessionId: string) => void;
}

// A control board: one compact weekly grid per department room, all on screen at
// once. Free cells read as availability; a block dragged from one card to another
// reassigns its room (live-validated, so clashes / capacity / farm needs flag
// immediately). Externals live in university-wide rooms, so only blackouts (which
// close every room) are overlaid here.
export function RoomBoards({
  placements, sessions, violations, walls, lang, selectedId, onMove, onSelect,
}: Props) {
  const conflicted = new Set(
    violations.filter((v) => v.severity === "hard").flatMap((v) => v.session_ids),
  );
  const soft = new Set(
    violations.filter((v) => v.severity === "soft").flatMap((v) => v.session_ids),
  );

  // sessions keyed by room → cell, and a per-room count for the card header.
  const byRoomCell = new Map<string, string[]>(); // `${room}:${day}:${box}`
  const countByRoom = new Map<string, number>();
  for (const [sid, p] of Object.entries(placements)) {
    const key = `${p.room_id}:${p.day}:${p.start_box}`;
    byRoomCell.set(key, [...(byRoomCell.get(key) ?? []), sid]);
    countByRoom.set(p.room_id, (countByRoom.get(p.room_id) ?? 0) + 1);
  }

  // Blackouts close every room; draw them on each card. (Externals are off-site.)
  const wallByCell = new Map<string, FixedEvent[]>();
  for (const w of walls) {
    if (w.kind !== "blackout") continue;
    const key = `${w.day}:${w.start_box}`;
    wallByCell.set(key, [...(wallByCell.get(key) ?? []), w]);
  }

  const onDrop = (room: string, day: number, box: number) => (e: React.DragEvent) => {
    e.preventDefault();
    const sid = e.dataTransfer.getData("text/session");
    if (sid) onMove(sid, day, box, room);
  };

  return (
    <div className="room-boards">
      {ROOMS.map((rm) => {
        const count = countByRoom.get(rm.id) ?? 0;
        const name = rm.name.split(" (")[0];
        return (
          <section key={rm.id} className="room-card">
            <header className="room-card-head">
              <span className="room-card-name">
                {name}{rm.id === FARM_ID && <span className="room-farm" title="computer farm"> 🖥</span>}
              </span>
              <span className="room-card-count">{count}</span>
            </header>
            <table className="grid room-grid">
              <thead>
                <tr>
                  <th className="time-col"></th>
                  {Array.from({ length: DAYS }, (_, d) => <th key={d}>{DAY_ABBR[lang][d]}</th>)}
                </tr>
              </thead>
              <tbody>
                {Array.from({ length: BOXES }, (_, box) => (
                  <tr key={box}>
                    <td className="time-col">{boxLabel(box).split("-")[0]}</td>
                    {Array.from({ length: DAYS }, (_, day) => {
                      const sids = byRoomCell.get(`${rm.id}:${day}:${box}`) ?? [];
                      const cellWalls = wallByCell.get(`${day}:${box}`) ?? [];
                      return (
                        <td key={day} onDragOver={(e) => e.preventDefault()} onDrop={onDrop(rm.id, day, box)}>
                          {cellWalls.map((w) => (
                            <div
                              key={w.id} className="wall wall-blackout"
                              style={{ height: Math.max(1, w.length_boxes) * ROW_H - 2 }}
                              title={w.label}
                            />
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
                            const style = {
                              height: span * ROW_H - 2,
                              width: `calc(${100 / sids.length}% - 2px)`,
                              insetInlineStart: `calc(${(100 * i) / sids.length}% + 1px)`,
                            } as const;
                            return (
                              <div
                                key={sid} className={cls} draggable={!fixed} style={style}
                                onDragStart={(e) => fixed
                                  ? e.preventDefault()
                                  : e.dataTransfer.setData("text/session", sid)}
                                onClick={() => onSelect(sid)}
                                title={m
                                  ? `${m.course_number} ${m.type}${m.group ? ` · ${m.group}` : ""}${fixed ? ` · ${t("fixedTag", lang)}` : ""}`
                                  : sid}
                              >
                                <div className="b-top">
                                  <span className="b-course">{m?.course_number ?? sid}</span>
                                  {fixed && <span className="b-lock" title={t("fixedTag", lang)}>🔒</span>}
                                </div>
                                <div className="b-sub">
                                  <span className="b-type">{m ? TYPE_ABBR[m.type] : ""}</span>
                                  {m?.group && <span className="b-group">{m.group}</span>}
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
          </section>
        );
      })}
    </div>
  );
}
