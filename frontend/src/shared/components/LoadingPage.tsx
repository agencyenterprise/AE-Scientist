export function LoadingPage() {
  return (
    <div className="min-h-screen bg-slate-950 flex flex-col items-center justify-center">
      <div className="flex flex-col items-center gap-6">
        {/* Animated spinner with gradient */}
        <div className="relative">
          <div className="h-16 w-16 rounded-full border-8 border-slate-800"></div>
          <div className="absolute inset-0 h-16 w-16 animate-spin rounded-full border-8 border-transparent border-t-sky-500 border-r-sky-400"></div>
        </div>

        {/* Loading text */}
        <div className="flex flex-col items-center gap-2">
          <p className="text-lg font-medium text-slate-200">Initializing</p>
          <p className="text-sm text-slate-400">Preparing your workspace...</p>
        </div>
      </div>
    </div>
  );
}
