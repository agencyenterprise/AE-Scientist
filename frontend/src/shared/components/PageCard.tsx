export function PageCard(props: { children: React.ReactNode }) {
  return (
    <section className="relative overflow-hidden rounded-2xl border border-slate-800/80 bg-slate-950/70 shadow-[0_30px_80px_-40px_rgba(14,165,233,0.7)] sm:rounded-[2.75rem] sm:shadow-[0_50px_140px_-60px_rgba(14,165,233,0.9)]">
      <div className="pointer-events-none absolute -left-[20%] -top-[35%] h-[200px] w-[200px] rounded-full bg-sky-500/20 blur-3xl sm:h-[420px] sm:w-[420px]" />
      <div className="pointer-events-none absolute -right-[25%] top-1/3 h-[180px] w-[180px] rounded-full bg-indigo-500/20 blur-3xl sm:h-[360px] sm:w-[360px]" />
      {props.children}
    </section>
  );
}
