export function ChatEmptyState() {
  return (
    <div className="h-full flex flex-col items-center justify-center text-center text-muted-foreground">
      <svg
        className="mx-auto h-12 w-12 text-muted-foreground/60 mb-4"
        fill="none"
        stroke="currentColor"
        viewBox="0 0 24 24"
      >
        <path
          strokeLinecap="round"
          strokeLinejoin="round"
          strokeWidth={2}
          d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z"
        />
      </svg>
      <p className="text-lg font-medium">Start a conversation</p>
      <p className="text-sm mt-1">Ask questions about your project or request improvements</p>
    </div>
  );
}
