/**
 * Shared date utility functions
 */
import { formatDistanceToNow, format, differenceInSeconds } from "date-fns";

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

/**
 * Formats a date string as full date and time (e.g., "Jan 15, 2024, 3:45:30 PM")
 * @param dateString - ISO date string
 * @returns Formatted date-time string
 */
export function formatDateTime(dateString: string): string {
  try {
    const date = new Date(dateString);
    return format(date, "PPpp");
  } catch {
    return dateString;
  }
}

/**
 * Formats the duration between two dates in short format (e.g., "2h 30m")
 * @param startDate - ISO date string (start time)
 * @param endDate - ISO date string (end time), defaults to current time if not provided
 * @returns Formatted duration string (e.g., "2h 30m", "45m", "1h 15m")
 */
export function formatDuration(startDate: string, endDate?: string | null): string {
  try {
    const start = new Date(startDate);
    const end = endDate ? new Date(endDate) : new Date();

    // Handle invalid dates
    if (isNaN(start.getTime()) || isNaN(end.getTime())) {
      return "-";
    }

    // Calculate difference in seconds
    const totalSeconds = differenceInSeconds(end, start);

    // Handle negative or zero duration
    if (totalSeconds <= 0) {
      return "0m";
    }

    // Calculate hours, minutes, seconds
    const hours = Math.floor(totalSeconds / 3600);
    const minutes = Math.floor((totalSeconds % 3600) / 60);
    const seconds = totalSeconds % 60;

    // Build result string with non-zero components only
    const parts: string[] = [];
    if (hours > 0) parts.push(`${hours}h`);
    if (minutes > 0) parts.push(`${minutes}m`);
    if (seconds > 0 && hours === 0 && minutes === 0) parts.push(`${seconds}s`);

    return parts.length > 0 ? parts.join(" ") : "0m";
  } catch {
    return "-";
  }
}
