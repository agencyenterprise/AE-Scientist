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
 * Formats bytes into human-readable file size
 * @param bytes - Number of bytes
 * @returns Formatted file size string (e.g., "1.5 MB")
 */
export function formatBytes(bytes: number): string {
  if (bytes === 0) return "0 Bytes";
  const k = 1024;
  const sizes = ["Bytes", "KB", "MB", "GB"];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + " " + sizes[i];
}
