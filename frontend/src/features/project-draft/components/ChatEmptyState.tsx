import { Sparkles } from "lucide-react";

export function ChatEmptyState() {
  return (
    <div className="h-full flex flex-col items-center justify-center text-center text-muted-foreground">
      <Sparkles className="mx-auto h-12 w-12 text-muted-foreground/60 mb-4" />
      <p className="text-lg font-medium">Use AI to improve your idea</p>
      <p className="text-sm mt-1">
        Ask questions, request changes, or get suggestions to refine your research
      </p>
    </div>
  );
}
