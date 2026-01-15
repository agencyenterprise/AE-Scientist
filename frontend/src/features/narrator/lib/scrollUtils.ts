/**
 * Scroll utilities - Pure functions for programmatic scrolling with sticky header awareness.
 */

/**
 * Scroll to a specific element within a scroll container, accounting for sticky headers.
 *
 * @param container - The scroll container element
 * @param elementId - The data-event-id or data-stage-id to scroll to
 * @param stickyHeaderSelector - CSS selector for sticky headers to calculate offset
 * @returns true if scrolled, false if element not found
 */
export function scrollToElement(
  container: HTMLElement | null,
  elementId: string,
  stickyHeaderSelector: string = "[data-sticky-header]"
): boolean {
  if (!container) return false;

  const element = container.querySelector(
    `[data-event-id="${elementId}"], [data-stage-id="${elementId}"]`
  );
  if (!element) return false;

  // Calculate total offset from all sticky headers
  const stickyHeaders = container.querySelectorAll(stickyHeaderSelector);
  const stickyOffset = Array.from(stickyHeaders).reduce((total, header) => {
    return total + header.getBoundingClientRect().height;
  }, 0);

  // Add some breathing room (16px)
  const totalOffset = stickyOffset + 16;

  // Get element position relative to container
  const elementRect = element.getBoundingClientRect();
  const containerRect = container.getBoundingClientRect();
  const relativeTop = elementRect.top - containerRect.top;
  const currentScroll = container.scrollTop;

  // Calculate target scroll position
  const targetScroll = currentScroll + relativeTop - totalOffset;

  container.scrollTo({
    top: Math.max(0, targetScroll),
    behavior: "smooth",
  });

  return true;
}

/**
 * Scroll to the bottom of a container (latest content).
 *
 * @param container - The scroll container element
 * @param animated - Whether to animate the scroll
 */
export function scrollToBottom(container: HTMLElement | null, animated: boolean = true): void {
  if (!container) return;

  container.scrollTo({
    top: container.scrollHeight,
    behavior: animated ? "smooth" : "auto",
  });
}

/**
 * Check if user is near the bottom of a scroll container.
 *
 * @param container - The scroll container element
 * @param threshold - Distance from bottom in pixels (default: 100)
 * @returns true if within threshold of bottom
 */
export function isNearBottom(container: HTMLElement | null, threshold: number = 100): boolean {
  if (!container) return false;

  const { scrollTop, scrollHeight, clientHeight } = container;
  const distanceFromBottom = scrollHeight - scrollTop - clientHeight;

  return distanceFromBottom <= threshold;
}

/**
 * Get the scroll container element from a ref or selector.
 *
 * @param containerRef - React ref to scroll container
 * @returns The scroll container element or null
 */
export function getScrollContainer(containerRef: React.RefObject<HTMLElement>): HTMLElement | null {
  return containerRef.current;
}

/**
 * Debounce function for scroll event handlers.
 *
 * @param fn - Function to debounce
 * @param delay - Delay in milliseconds
 * @returns Debounced function
 */
export function debounce<T extends (...args: unknown[]) => unknown>(
  fn: T,
  delay: number
): (...args: Parameters<T>) => void {
  let timeoutId: ReturnType<typeof setTimeout> | null = null;

  return (...args: Parameters<T>) => {
    if (timeoutId) {
      clearTimeout(timeoutId);
    }
    timeoutId = setTimeout(() => {
      fn(...args);
    }, delay);
  };
}
