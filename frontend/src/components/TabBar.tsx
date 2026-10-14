import { NavLink } from "react-router-dom";

export interface TabDef {
  id: string;
  label: string;
}

/**
 * Segmented top-level navigation for review sections (HIG: prefer tab-style
 * navigation for top-level sections; ≤5 items, no overflow).
 */
export function TabBar({ tabs, active }: { tabs: TabDef[]; active: string }) {
  return (
    <div
      role="tablist"
      aria-label="Review sections"
      className="flex gap-1 overflow-x-auto border-b border-separator"
    >
      {tabs.map((t) => {
        const selected = t.id === active;
        return (
          <NavLink
            key={t.id}
            role="tab"
            aria-selected={selected}
            to={`?tab=${t.id}`}
            className={`relative -mb-px shrink-0 px-4 py-2.5 text-sm font-medium whitespace-nowrap transition-colors ${
              selected ? "text-accent" : "text-secondary-label hover:text-label"
            }`}
          >
            {t.label}
            {selected && (
              <span
                className="absolute inset-x-3 -bottom-px h-0.5 rounded-full bg-accent"
                aria-hidden
              />
            )}
          </NavLink>
        );
      })}
    </div>
  );
}
