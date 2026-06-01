import type { Placement, Violation } from "../types";
import { DAY_NAMES, boxLabel, type Lang } from "../i18n";

const BOXES = 10; // 08:30..18:30
const DAYS = 5; // Sun..Thu

interface Props {
  placements: Record<string, Placement>;
  violations: Violation[];
  lang: Lang;
}

// The weekly grid: the centerpiece view. Each placed session renders as a block
// in its (day, box) cell. Sessions touched by a hard violation glow red.
export function WeeklyGrid({ placements, violations, lang }: Props) {
  const conflicted = new Set(
    violations.filter((v) => v.severity === "hard").flatMap((v) => v.session_ids),
  );

  // cell -> session ids that start there
  const byCell = new Map<string, string[]>();
  for (const [sid, p] of Object.entries(placements)) {
    const key = `${p.day}:${p.start_box}`;
    byCell.set(key, [...(byCell.get(key) ?? []), sid]);
  }

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
                <td key={day}>
                  {sids.map((sid) => (
                    <div
                      key={sid}
                      className={`block${conflicted.has(sid) ? " conflict" : ""}`}
                      title={sid}
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
