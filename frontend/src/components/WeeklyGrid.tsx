import type { Placement, Violation } from "../types";
import { DAY_NAMES, boxLabel, type Lang } from "../i18n";

const BOXES = 10; // 08:30..18:30
const DAYS = 5; // Sun..Thu

interface Props {
  placements: Record<string, Placement>;
  violations: Violation[];
  lang: Lang;
  onMove: (sessionId: string, day: number, startBox: number) => void;
}

// The weekly grid: the centerpiece, editable view. Each placed session renders
// as a draggable block in its (day, start_box) cell. Dropping it on another cell
// moves it (keeping its room); the parent re-validates live. Sessions touched by
// a hard violation glow red.
export function WeeklyGrid({ placements, violations, lang, onMove }: Props) {
  const conflicted = new Set(
    violations.filter((v) => v.severity === "hard").flatMap((v) => v.session_ids),
  );

  const byCell = new Map<string, string[]>();
  for (const [sid, p] of Object.entries(placements)) {
    const key = `${p.day}:${p.start_box}`;
    byCell.set(key, [...(byCell.get(key) ?? []), sid]);
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
          {Array.from({ length: DAYS }, (_, d) => (
            <th key={d}>{DAY_NAMES[lang][d]}</th>
          ))}
        </tr>
      </thead>
      <tbody>
        {Array.from({ length: BOXES }, (_, box) => (
          <tr key={box}>
            <td className="time-col">{boxLabel(box)}</td>
            {Array.from({ length: DAYS }, (_, day) => {
              const sids = byCell.get(`${day}:${box}`) ?? [];
              return (
                <td
                  key={day}
                  onDragOver={(e) => e.preventDefault()}
                  onDrop={onDrop(day, box)}
                >
                  {sids.map((sid) => (
                    <div
                      key={sid}
                      className={`block${conflicted.has(sid) ? " conflict" : ""}`}
                      title={sid}
                      draggable
                      onDragStart={(e) => e.dataTransfer.setData("text/session", sid)}
                    >
                      {sid}
                    </div>
                  ))}
                </td>
              );
            })}
          </tr>
        ))}
      </tbody>
    </table>
  );
}
