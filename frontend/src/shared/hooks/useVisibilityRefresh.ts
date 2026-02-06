import { useEffect, useRef } from "react";

/**
 * Hook that triggers a callback when the tab becomes visible.
 * Useful for refreshing stale data when users return to the tab.
 *
 * @param onVisible - Callback to execute when tab becomes visible
 * @param options - Configuration options
 * @param options.enabled - Whether the hook is active (default: true)
 * @param options.debounceMs - Minimum time between refreshes (default: 1000ms)
 */
export function useVisibilityRefresh(
  onVisible: () => void,
  options: { enabled?: boolean; debounceMs?: number } = {}
) {
  const { enabled = true, debounceMs = 1000 } = options;
  const lastRefreshRef = useRef<number>(0);

  useEffect(() => {
    if (!enabled) return;

    const handleVisibilityChange = () => {
      if (document.visibilityState === "visible") {
        const now = Date.now();
        // Debounce to avoid rapid refreshes
        if (now - lastRefreshRef.current >= debounceMs) {
          lastRefreshRef.current = now;
          onVisible();
        }
      }
    };

    document.addEventListener("visibilitychange", handleVisibilityChange);
    return () => {
      document.removeEventListener("visibilitychange", handleVisibilityChange);
    };
  }, [onVisible, enabled, debounceMs]);
}
