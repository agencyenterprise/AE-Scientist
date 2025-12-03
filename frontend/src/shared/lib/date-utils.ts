/**
 * Shared date utility functions
 */
import { formatDistanceToNow, format } from "date-fns";

/**
 * Formats a date string as relative time (e.g., "2 hours ago")
 * @param dateString - ISO date string
 * @returns Formatted relative time string
 */
export function formatRelativeTime(dateString: string): string {
  try {
    const date = new Date(dateString);
    return formatDistanceToNow(date, { addSuffix: true });
  } catch {
    return dateString;
  }
}

/**
 * Formats a date string as "MM/DD/YYYY, HH:MM:SS AM/PM"
 * @param dateString - ISO date string
 * @returns Formatted timestamp string
 */
export function formatLaunchedTimestamp(dateString: string): string {
  try {
    const date = new Date(dateString);
    return format(date, "MM/dd/yyyy, hh:mm:ss a");
  } catch {
    return dateString;
  }
}
