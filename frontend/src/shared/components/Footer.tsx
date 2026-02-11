"use client";

export function Footer() {
  return (
    <footer className="border-t border-slate-800 bg-slate-950/50 px-4 py-3 sm:px-8">
      <div className="flex items-center justify-center text-sm text-slate-500">
        <span>
          Built by{" "}
          <a
            href="https://ae.studio"
            target="_blank"
            rel="noopener noreferrer"
            className="text-slate-400 hover:text-white hover:underline transition-colors"
          >
            AE Studio
          </a>
        </span>
        <span className="mx-2">·</span>
        <span>
          Funded by{" "}
          <a
            href="https://www.flourishingfuturefoundation.org"
            target="_blank"
            rel="noopener noreferrer"
            className="text-slate-400 hover:text-white hover:underline transition-colors"
          >
            FFF
          </a>
        </span>
      </div>
    </footer>
  );
}
