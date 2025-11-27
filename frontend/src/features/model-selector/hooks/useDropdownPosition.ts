import { RefObject, useCallback, useEffect, useRef, useState } from "react";

/**
 * Coordinates for positioning the dropdown relative to the viewport.
 */
export interface DropdownCoords {
  /** Distance from the top of the viewport (used when verticalPosition is "below") */
  top: number;
  /** Distance from the bottom of the viewport (used when verticalPosition is "above") */
  bottom: number;
  /** Distance from the left of the viewport (used when position is "left") */
  left: number;
  /** Distance from the right of the viewport (used when position is "right") */
  right: number;
  /** Maximum height available for the dropdown */
  maxHeight: number;
}

/**
 * Return type for the useDropdownPosition hook.
 */
interface UseDropdownPositionReturn {
  /** Ref to attach to the trigger button element */
  buttonRef: RefObject<HTMLButtonElement | null>;
  /** Ref to attach to the search input for auto-focus */
  searchInputRef: RefObject<HTMLInputElement | null>;
  /** Ref to attach to the currently selected model for auto-scroll */
  selectedModelRef: RefObject<HTMLButtonElement | null>;
  /** Whether the dropdown is currently open */
  isOpen: boolean;
  /** Which side the dropdown should align to ("left" or "right") */
  position: "left" | "right";
  /** Whether dropdown opens above or below the button */
  verticalPosition: "above" | "below";
  /** The calculated coordinates for positioning, or null when closed */
  coords: DropdownCoords | null;
  /** Toggles the dropdown open/closed */
  toggle: () => void;
  /** Closes the dropdown */
  close: () => void;
}

/** Width of the dropdown in pixels (w-64 = 16rem = 256px) */
const DROPDOWN_WIDTH = 256;
/** Margin between the button and dropdown (mt-1 = 4px) */
const DROPDOWN_MARGIN = 4;
/** Minimum margin from viewport edge */
const VIEWPORT_MARGIN = 16;
/** Minimum height needed for dropdown to be usable */
const MIN_DROPDOWN_HEIGHT = 200;
/** Maximum height for dropdown */
const MAX_DROPDOWN_HEIGHT = 400;

/**
 * Hook for managing dropdown positioning with viewport-aware placement.
 *
 * Features:
 * - Automatically positions dropdown left or right based on available space
 * - Recalculates position on window resize
 * - Auto-focuses search input when opened
 * - Auto-scrolls to selected item when opened
 *
 * @returns Object containing refs, state, and control functions
 *
 * @example
 * ```tsx
 * const { buttonRef, isOpen, coords, position, toggle, close } = useDropdownPosition();
 *
 * return (
 *   <>
 *     <button ref={buttonRef} onClick={toggle}>Open</button>
 *     {isOpen && coords && (
 *       <div style={{ position: 'fixed', top: coords.top, [position]: coords[position] }}>
 *         Dropdown content
 *       </div>
 *     )}
 *   </>
 * );
 * ```
 */
export function useDropdownPosition(): UseDropdownPositionReturn {
  const buttonRef = useRef<HTMLButtonElement>(null);
  const searchInputRef = useRef<HTMLInputElement>(null);
  const selectedModelRef = useRef<HTMLButtonElement>(null);

  const [isOpen, setIsOpen] = useState(false);
  const [position, setPosition] = useState<"left" | "right">("left");
  const [verticalPosition, setVerticalPosition] = useState<"above" | "below">("below");
  const [coords, setCoords] = useState<DropdownCoords | null>(null);

  const calculatePosition = useCallback((): void => {
    if (!buttonRef.current) return;

    const buttonRect = buttonRef.current.getBoundingClientRect();
    const viewportWidth = window.innerWidth;
    const viewportHeight = window.innerHeight;
    const spaceOnRight = viewportWidth - buttonRect.right;

    // Calculate space above and below
    const spaceBelow = viewportHeight - buttonRect.bottom - DROPDOWN_MARGIN - VIEWPORT_MARGIN;
    const spaceAbove = buttonRect.top - DROPDOWN_MARGIN - VIEWPORT_MARGIN;

    // Prefer opening above if there's enough space (better UX for bottom-positioned buttons)
    const openAbove = spaceAbove >= MIN_DROPDOWN_HEIGHT;

    const availableHeight = openAbove ? spaceAbove : spaceBelow;
    const maxHeight = Math.min(availableHeight, MAX_DROPDOWN_HEIGHT);
    const top = openAbove ? 0 : buttonRect.bottom + DROPDOWN_MARGIN;
    const bottom = openAbove ? viewportHeight - buttonRect.top + DROPDOWN_MARGIN : 0;

    setVerticalPosition(openAbove ? "above" : "below");

    if (spaceOnRight < DROPDOWN_WIDTH) {
      setPosition("right");
      setCoords({
        top,
        bottom,
        left: 0,
        right: viewportWidth - buttonRect.right,
        maxHeight,
      });
    } else {
      setPosition("left");
      setCoords({
        top,
        bottom,
        left: buttonRect.left,
        right: 0,
        maxHeight,
      });
    }
  }, []);

  const toggle = useCallback((): void => {
    if (!isOpen) {
      calculatePosition();
      setTimeout(() => {
        searchInputRef.current?.focus();
        selectedModelRef.current?.scrollIntoView({
          behavior: "smooth",
          block: "center",
        });
      }, 50);
    } else {
      setCoords(null);
    }
    setIsOpen(!isOpen);
  }, [isOpen, calculatePosition]);

  const close = useCallback((): void => {
    setIsOpen(false);
    setCoords(null);
  }, []);

  // Recalculate position on window resize
  useEffect(() => {
    if (!isOpen || !coords) return;

    const handleResize = (): void => {
      calculatePosition();
    };

    window.addEventListener("resize", handleResize);
    return () => window.removeEventListener("resize", handleResize);
  }, [isOpen, coords, calculatePosition]);

  return {
    buttonRef,
    searchInputRef,
    selectedModelRef,
    isOpen,
    position,
    verticalPosition,
    coords,
    toggle,
    close,
  };
}
