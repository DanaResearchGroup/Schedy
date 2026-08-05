import { useEffect, useRef, useState } from "react";

export interface Option {
  value: string;
  label: string;
}

interface Props {
  label: string;
  /** Shown on the closed button while nothing is ticked. */
  allLabel: string;
  options: Option[];
  selected: string[];
  onChange: (next: string[]) => void;
}

// A checkbox dropdown. Ticking nothing means "everything", so the closed button
// reads as what the filter currently does rather than as an empty selection.
export function MultiSelect({ label, allLabel, options, selected, onChange }: Props) {
  const [open, setOpen] = useState(false);
  const box = useRef<HTMLDivElement>(null);

  // The panel floats over the grid, so an outside click or Escape closes it.
  useEffect(() => {
    if (!open) return;
    const onDown = (e: MouseEvent) => {
      if (!box.current?.contains(e.target as Node)) setOpen(false);
    };
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setOpen(false);
    };
    document.addEventListener("mousedown", onDown);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDown);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  const toggle = (value: string) =>
    onChange(selected.includes(value)
      ? selected.filter((s) => s !== value)
      : [...selected, value]);

  const chosen = options.filter((o) => selected.includes(o.value));
  const summary = chosen.length === 0 ? allLabel
    : chosen.length === 1 ? chosen[0].label
    : `${chosen[0].label} +${chosen.length - 1}`;

  return (
    <div className={`ms${open ? " open" : ""}`} ref={box}>
      <button
        type="button" aria-expanded={open} title={label}
        className={`ms-btn${chosen.length > 0 ? " on" : ""}`}
        onClick={() => setOpen(!open)}
      >
        <span className="ms-name">{label}</span>
        <span className="ms-summary">{summary}</span>
        <span className="ms-caret" aria-hidden="true">▾</span>
      </button>
      {open && (
        <div className="ms-menu" role="group" aria-label={label}>
          {options.map((o) => (
            <label key={o.value} className="ms-item">
              <input
                type="checkbox" checked={selected.includes(o.value)}
                onChange={() => toggle(o.value)}
              />
              <span>{o.label}</span>
            </label>
          ))}
          {options.length === 0 && <div className="ms-item muted">—</div>}
        </div>
      )}
    </div>
  );
}
