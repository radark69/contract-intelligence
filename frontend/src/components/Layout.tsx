import { useEffect, useState, type ReactNode } from "react";

function ThemeToggle() {
  const [dark, setDark] = useState(
    () => document.documentElement.classList.contains("dark"),
  );
  function toggle() {
    const next = !dark;
    document.documentElement.classList.toggle("dark", next);
    localStorage.setItem("theme", next ? "dark" : "light");
    setDark(next);
  }
  return (
    <button
      type="button"
      onClick={toggle}
      aria-label={dark ? "Switch to light appearance" : "Switch to dark appearance"}
      className="grid size-9 place-items-center rounded-full text-secondary-label transition-colors hover:bg-surface-2 hover:text-label"
    >
      {dark ? "☀︎" : "☾"}
    </button>
  );
}

/**
 * App shell: skip link, sticky translucent header with content scrolling
 * beneath (HIG: controls float above content layer; DESIGN.md §5).
 */
export function Layout({ children }: { children: ReactNode }) {
  useEffect(() => {
    document.title = "DBS Contract Reviewer";
  }, []);

  return (
    <div className="min-h-dvh">
      <a
        href="#main"
        className="sr-only focus:not-sr-only focus:fixed focus:top-2 focus:left-2 focus:z-50 focus:rounded-lg focus:bg-accent focus:px-3 focus:py-2 focus:text-sm focus:text-white"
      >
        Skip to content
      </a>
      <header className="sticky top-0 z-40 border-b border-separator bg-background/75 backdrop-blur-xl supports-[backdrop-filter]:bg-background/70">
        <div className="mx-auto flex h-14 max-w-5xl items-center justify-between px-4 sm:px-6">
          <a href="/" className="flex items-center gap-2.5 font-semibold">
            <span
              aria-hidden
              className="grid size-7 place-items-center rounded-lg bg-accent text-sm font-bold text-white"
            >
              D
            </span>
            <span>Contract Reviewer</span>
          </a>
          <ThemeToggle />
        </div>
      </header>
      <main id="main" className="mx-auto max-w-5xl px-4 py-8 sm:px-6">
        {children}
      </main>
    </div>
  );
}
