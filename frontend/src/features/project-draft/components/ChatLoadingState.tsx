export function ChatLoadingState() {
  return (
    <div className="text-center text-muted-foreground mt-8">
      <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-[var(--primary)] mx-auto mb-2"></div>
      <p className="text-sm">Loading chat history...</p>
    </div>
  );
}
