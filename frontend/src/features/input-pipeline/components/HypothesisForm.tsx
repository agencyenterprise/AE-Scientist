"use client";

interface HypothesisFormProps {
  title: string;
  idea: string;
  onTitleChange: (value: string) => void;
  onIdeaChange: (value: string) => void;
  disabled?: boolean;
}

export function HypothesisForm({
  title,
  idea,
  onTitleChange,
  onIdeaChange,
  disabled = false,
}: HypothesisFormProps) {
  return (
    <div className="space-y-6">
      <div className="space-y-2">
        <label
          className="text-sm font-semibold uppercase tracking-wide text-slate-300"
          htmlFor="title"
        >
          Research idea title
        </label>
        <input
          id="title"
          placeholder="Summarize the scientific direction in one line"
          className="w-full rounded-2xl border border-slate-800 bg-slate-950/70 px-4 py-3 text-base text-slate-100 placeholder:text-slate-500 outline-none transition focus:border-sky-500/50 focus:ring-2 focus:ring-sky-400/20 disabled:opacity-50"
          value={title}
          onChange={event => onTitleChange(event.target.value)}
          disabled={disabled}
        />
      </div>

      <div className="space-y-2">
        <label
          className="text-sm font-semibold uppercase tracking-wide text-slate-300"
          htmlFor="idea"
        >
          Research idea details
        </label>
        <textarea
          id="idea"
          placeholder="Explain the objective, expected insight, and why it matters. The more detail you include, the more context the AI Scientist has to work with."
          className="w-full min-h-[220px] resize-none rounded-3xl border border-slate-800 bg-slate-950/70 px-5 py-4 text-base leading-relaxed text-slate-100 placeholder:text-slate-500 outline-none transition focus:border-sky-500/50 focus:ring-2 focus:ring-sky-400/20 disabled:opacity-50 md:min-h-[260px]"
          rows={8}
          value={idea}
          onChange={event => onIdeaChange(event.target.value)}
          disabled={disabled}
        />
      </div>
    </div>
  );
}
