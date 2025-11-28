interface ChatErrorBannerProps {
  error: string;
}

export function ChatErrorBanner({ error }: ChatErrorBannerProps) {
  return (
    <div className="px-4 py-2 bg-destructive/10 border-b border-destructive/30">
      <p className="text-sm text-destructive">{error}</p>
    </div>
  );
}
