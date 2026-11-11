import Link from "next/link";

export function Seal({ className = "" }: { className?: string }) {
  return (
    <svg viewBox="0 0 40 40" className={className} aria-hidden="true">
      <circle cx="20" cy="20" r="18" fill="none" stroke="currentColor" strokeWidth="1.4" />
      <circle cx="20" cy="20" r="14.5" fill="none" stroke="currentColor" strokeWidth="0.7" strokeDasharray="1.2 1.6" />
      <path d="M13 20.5l4.6 4.6L27.5 15" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

export function SiteHeader() {
  return (
    <header className="mx-auto w-full max-w-6xl px-6 pt-6">
      <div className="flex items-end justify-between gap-6 pb-3">
        <Link href="/" className="group flex items-center gap-2.5 text-ink">
          <Seal className="h-8 w-8 text-verified transition-transform duration-500 group-hover:rotate-[-14deg]" />
          <span className="font-display text-[1.9rem] leading-none tracking-tight italic">Vouch</span>
          <span className="mb-0.5 hidden self-end font-mono text-[0.65rem] tracking-widest text-ink-faint uppercase sm:inline">
            research integrity
          </span>
        </Link>
        <nav className="flex items-center gap-5 text-sm text-ink-soft">
          <Link href="/" className="hover:text-ink">
            Check
          </Link>
          <Link href="/research" className="hover:text-ink">
            Research
          </Link>
          <a href="https://github.com/Priyanshu-byte-coder/vouch" className="hover:text-ink" target="_blank" rel="noreferrer">
            Code
          </a>
        </nav>
      </div>
      <div className="rule-double" />
    </header>
  );
}
