import { useState } from "react";
import type { FixedEvent, Placement, SessionMeta, Violation } from "../types";
import { ROOMS } from "../types";
import { DAY_ABBR, boxLabel, t, type Lang } from "../i18n";

const BOXES = 10; // 08:30..18:30
const DAYS = 5; // Sun..Thu
const ROW_H = 34; // px per academic-hour row (keep in sync with .room-grid td height)
const FARM_ID = "room2"; // the computer-farm room
const TOTAL_BOXES = DAYS * BOXES;

const TYPE_ABBR: Record<string, string> = { lecture: "L", exercise: "T", lab: "Lab" };

// Room-board cells are narrow; a short cap plus CSS ellipsis keeps names tidy.
const MAX_NAME = 16;
const shortName = (s?: string) =>
  !s ? "" : s.length > MAX_NAME ? `${s.slice(0, MAX_NAME - 1)}…` : s;

// What a session needs from a room — captured on drag-start so the boards can
// dim rooms that can't host it before the planner drops.
interface DragNeed {
  enrollment: number;
  needsFarm: boolean;
}

interface Props {
  placements: Record<string, Placement>;
  sessions: Record<string, SessionMeta>;
  violations: Violation[];
  walls: FixedEvent[];
  parked: string[];
  lang: Lang;
  selectedId: string | null;
  names?: Record<string, string>;
  onMove: (sessionId: string, day: number, startBox: number, room: string) => void;
  onPark: (sessionId: string) => void;
  onSelect: (sessionId: string) => void;
  validateDrop?: (sessionId: string, day: number, startBox: number, room: string) => boolean;
}

function fits(room: { capacity: number; farm?: boolean }, need: DragNeed | null): boolean {
  if (!need) return true;
  if (need.needsFarm && !room.farm) return false;
  return room.capacity >= need.enrollment;
}

// A control board: one compact weekly grid per department room, all on screen at
// once. Free cells read as availability; a block dragged from one card to another
// reassigns its room (live-validated). While dragging, rooms that can't host the
// session dim out. A session dragged to the Parked lane is set aside (unplaced)
// until dropped back onto a room. Externals live in university-wide rooms, so
// only blackouts (which close every room) are overlaid here.
export function RoomBoards({
  placements, sessions, violations, walls, parked, lang, selectedId, names,
  onMove, onPark, onSelect, validateDrop,
}: Props) {
  const [need, setNeed] = useState<DragNeed | null>(null);
  const [dragSid, setDragSid] = useState<string | null>(null);

  const conflicted = new Set(
    violations.filter((v) => v.severity === "hard").flatMap((v) => v.session_ids),
  );
  const soft = new Set(
    violations.filter((v) => v.severity === "soft").flatMap((v) => v.session_ids),
  );

  // sessions keyed by room → cell, plus used box-hours per room for utilization.
  const byRoomCell = new Map<string, string[]>(); // `${room}:${day}:${box}`
  const usedByRoom = new Map<string, number>();
  for (const [sid, p] of Object.entries(placements)) {
    const key = `${p.room_id}:${p.day}:${p.start_box}`;
    byRoomCell.set(key, [...(byRoomCell.get(key) ?? []), sid]);
    const span = Math.max(1, sessions[sid]?.length_boxes ?? 1);
    usedByRoom.set(p.room_id, (usedByRoom.get(p.room_id) ?? 0) + span);
  }

  // Blackouts close every room; draw them on each card and subtract their hours
  // from each room's available capacity. (Externals are off-site.)
  const wallByCell = new Map<string, FixedEvent[]>();
  let blackoutBoxes = 0;
  for (const w of walls) {
    if (w.kind !== "blackout") continue;
    blackoutBoxes += Math.max(1, w.length_boxes);
    const key = `${w.day}:${w.start_box}`;
    wallByCell.set(key, [...(wallByCell.get(key) ?? []), w]);
  }
  const available = Math.max(1, TOTAL_BOXES - blackoutBoxes);

  // Department-wide rollup for the summary strip.
  const roomsInUse = ROOMS.filter((r) => (usedByRoom.get(r.id) ?? 0) > 0).length;
  const totalUsed = [...usedByRoom.values()].reduce((a, b) => a + b, 0);
  const totalCap = ROOMS.length * available;
  const deptPct = Math.round((totalUsed / totalCap) * 100);

  const startDrag = (sid: string) => {
    const m = sessions[sid];
    setNeed({ enrollment: m?.enrollment ?? 0, needsFarm: m?.needs_farm ?? false });
    setDragSid(sid);
  };
  const endDrag = () => { setNeed(null); setDragSid(null); };

  const onCellDrop = (room: string, day: number, box: number, eligible: boolean) =>
    (e: React.DragEvent) => {
      e.preventDefault();
      endDrag();
      if (!eligible) return;
      const sid = e.dataTransfer.getData("text/session");
      if (sid) onMove(sid, day, box, room);
    };

  const onParkDrop = (e: React.DragEvent) => {
    e.preventDefault();
    endDrag();
    const sid = e.dataTransfer.getData("text/session");
    if (sid) onPark(sid);
  };

  const block = (sid: string, sids: string[], i: number) => {
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
        onDragStart={(e) => {
          if (fixed) { e.preventDefault(); return; }
          e.dataTransfer.setData("text/session", sid);
          startDrag(sid);
        }}
        onDragEnd={endDrag}
        onClick={() => onSelect(sid)}
        title={m
          ? `${m.course_number} ${m.type}${m.group ? ` · ${m.group}` : ""}${fixed ? ` · ${t("fixedTag", lang)}` : ""}`
          : sid}
      >
        <div className="b-top">
          <span className="b-course">{m?.course_number ?? sid}</span>
          {fixed && <span className="b-lock" title={t("fixedTag", lang)}>🔒</span>}
        </div>
        {m && names?.[m.course_number] && (
          <div className="b-name" dir="rtl">{shortName(names[m.course_number])}</div>
        )}
        <div className="b-sub">
          <span className="b-type">{m ? TYPE_ABBR[m.type] : ""}</span>
          {m?.group && <span className="b-group">{m.group}</span>}
          {m?.is_remote && <span className="b-zoom">⚡</span>}
        </div>
      </div>
    );
  };

  return (
    <div className="room-boards-wrap">
      <div className="dept-summary">
        <span className="dept-stat"><b>{roomsInUse}/{ROOMS.length}</b> {t("statRoomsInUse", lang)}</span>
        <span className="dept-stat"><b>{totalUsed}h</b> / {totalCap}h {t("statBooked", lang)}</span>
        <span className="dept-stat"><b>{deptPct}%</b> {t("statUtilization", lang)}</span>
      </div>
      <div className="room-boards">
        {ROOMS.map((rm) => {
          const used = usedByRoom.get(rm.id) ?? 0;
          const pct = Math.min(100, Math.round((used / available) * 100));
          const eligible = fits(rm, need);
          const name = rm.name.split(" (")[0];
          const cardCls = [
            "room-card",
            need ? (eligible ? "drop-ok" : "ineligible") : "",
          ].join(" ").trim();
          const whyBlocked = !eligible && need
            ? (need.needsFarm && !rm.farm ? t("needsFarmShort", lang) : t("tooSmall", lang))
            : undefined;
          return (
            <section key={rm.id} className={cardCls} title={whyBlocked}>
              <header className="room-card-head">
                <span className="room-card-name">
                  {name}{rm.id === FARM_ID && <span className="room-farm" title="computer farm"> 🖥</span>}
                </span>
                <span className="room-card-seats">{rm.capacity} {t("seats", lang)}</span>
              </header>
              <div className="room-util" title={`${pct}%`}>
                <div className="room-util-bar"><span style={{ width: `${pct}%` }} /></div>
                <span className="room-util-txt">{used}h · {Math.max(0, available - used)} {t("free", lang)}</span>
              </div>
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
                        const hint = dragSid && eligible && validateDrop
                          ? (validateDrop(dragSid, day, box, rm.id) ? "cell-ok" : "cell-bad")
                          : undefined;
                        return (
                          <td key={day} className={hint}
                            onDragOver={(e) => { if (eligible) e.preventDefault(); }}
                            onDrop={onCellDrop(rm.id, day, box, eligible)}>
                            {cellWalls.map((w) => (
                              <div
                                key={w.id} className="wall wall-blackout"
                                style={{ height: Math.max(1, w.length_boxes) * ROW_H - 2 }}
                                title={w.label}
                              />
                            ))}
                            {sids.map((sid, i) => block(sid, sids, i))}
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

      <div className="parked-lane" onDragOver={(e) => e.preventDefault()} onDrop={onParkDrop}>
        <div className="parked-head">
          <strong>{t("parked", lang)}</strong>
          <span className="parked-count">{parked.length}</span>
        </div>
        {parked.length === 0 ? (
          <p className="parked-hint">{t("parkHint", lang)}</p>
        ) : (
          <div className="parked-chips">
            {parked.map((sid) => {
              const m = sessions[sid];
              return (
                <div
                  key={sid} className="parked-chip" draggable
                  onDragStart={(e) => { e.dataTransfer.setData("text/session", sid); startDrag(sid); }}
                  onDragEnd={endDrag}
                  onClick={() => onSelect(sid)}
                  title={m ? `${m.course_number} ${m.type}${m.group ? ` · ${m.group}` : ""}` : sid}
                >
                  <span className="b-course">{m?.course_number ?? sid}</span>
                  <span className="b-type">{m ? TYPE_ABBR[m.type] : ""}</span>
                  {m?.group && <span className="b-group">{m.group}</span>}
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
