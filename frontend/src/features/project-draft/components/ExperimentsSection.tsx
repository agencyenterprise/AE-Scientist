import ReactMarkdown from "react-markdown";

import { markdownComponents } from "../utils/markdownComponents";

interface ExperimentsSectionProps {
  experiments: string[];
}

export function ExperimentsSection({ experiments }: ExperimentsSectionProps) {
  return (
    <div>
      <h3 className="text-xs font-semibold text-primary uppercase tracking-widest mb-4">
        Experiments
      </h3>
      <div className="space-y-3">
        {experiments.map((experiment, idx) => (
          <article
            key={idx}
            className="group overflow-hidden rounded-xl border border-border bg-muted/50 p-4 transition hover:border-primary/40"
          >
            <div className="flex items-start gap-3">
              <span className="inline-flex items-center justify-center w-7 h-7 rounded-full bg-primary text-primary-foreground text-xs font-bold flex-shrink-0 shadow-sm">
                {idx + 1}
              </span>
              <div className="flex-1 text-sm text-foreground leading-relaxed">
                <ReactMarkdown components={markdownComponents}>{experiment}</ReactMarkdown>
              </div>
            </div>
          </article>
        ))}
      </div>
    </div>
  );
}
