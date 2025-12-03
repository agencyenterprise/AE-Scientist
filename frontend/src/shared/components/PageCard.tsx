export function PageCard(props: { children: React.ReactNode }) {
  return (
    <section className="relative overflow-hidden rounded-[2.75rem] border border-slate-800/80 bg-slate-950/70 shadow-[0_50px_140px_-60px_rgba(14,165,233,0.9)]">
      <div className="pointer-events-none absolute -left-[20%] -top-[35%] h-[420px] w-[420px] rounded-full bg-sky-500/20 blur-3xl" />
      <div className="pointer-events-none absolute -right-[25%] top-1/3 h-[360px] w-[360px] rounded-full bg-indigo-500/20 blur-3xl" />
      {props.children}
    </section>
  );
}
