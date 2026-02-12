import { MessageCircle } from "lucide-react";

export function ChatEmptyState() {
  return (
    <div className="h-full flex flex-col items-center justify-center text-center text-muted-foreground">
      <MessageCircle className="mx-auto h-12 w-12 text-muted-foreground/60 mb-4" />
      <p className="text-lg font-medium">Refine your research idea</p>
      <p className="text-sm mt-1">
        Discuss your hypothesis to shape it into an executable experiment
      </p>
    </div>
  );
}
