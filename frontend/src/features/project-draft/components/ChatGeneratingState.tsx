export function ChatGeneratingState() {
  return (
    <div className="flex-shrink-0 border-t border-border bg-muted">
      <div className="px-4 py-2">
        <div className="text-center">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary mx-auto mb-2"></div>
          <p className="text-sm font-medium text-foreground">Project Draft Generating</p>
          <p className="text-xs text-muted-foreground mt-1">
            Please wait while the project draft is being generated. Chat will be available once
            complete.
          </p>
        </div>
      </div>
    </div>
  );
}
