/**
 * SSE frame type.
 *
 * SSE format:
 *   event: event_type
 *   data: payload
 */
export type SseFrame = {
  event: string;
  data: string;
};

/**
 * Generator that reads SSE frames from a byte stream.
 *
 * Responsibilities:
 * - Buffer management
 * - Text decoding
 * - Frame boundary detection (\n\n)
 * - Cleanup on exit
 *
 * Does NOT know about:
 * - JSON parsing
 * - Event types
 * - Domain logic
 */
export async function* readSseFrames(
  stream: ReadableStream<Uint8Array>,
  signal?: AbortSignal
): AsyncGenerator<string> {
  const reader = stream.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  try {
    while (true) {
      // Check for cancellation
      if (signal?.aborted) {
        return;
      }

      const { value, done } = await reader.read();
      if (done) {
        return;
      }

      // Accumulate decoded text
      buffer += decoder.decode(value, { stream: true });

      // Yield complete frames
      let boundary;
      while ((boundary = buffer.indexOf("\n\n")) !== -1) {
        const frame = buffer.slice(0, boundary);
        buffer = buffer.slice(boundary + 2);

        if (frame.trim()) {
          yield frame;
        }
      }
    }
  } finally {
    reader.releaseLock();
  }
}

/**
 * Parses a raw SSE frame string into structured event data.
 *
 * SSE format:
 *   event: event_type
 *   data: payload
 *
 * Returns null for invalid frames.
 */
export function parseNarratorSseFrame(frame: string): SseFrame | null {
  const lines = frame.split("\n");
  let eventType = "message"; // SSE default
  let eventData = "";

  for (const line of lines) {
    if (line.startsWith("event: ")) {
      eventType = line.slice(7).trim();
    } else if (line.startsWith("data: ")) {
      eventData = line.slice(6);
    }
  }

  if (!eventData) {
    return null;
  }

  return { event: eventType, data: eventData };
}

/**
 * Alternative parser for research run SSE frames.
 * These only use the data field and no event type.
 * Note: parsing of the eventData is left to the caller.
 */
export function parseResearchRunSseFrame(frame: string): SseFrame | null {
  const lines = frame.split("\n");
  for (const line of lines) {
    if (!line.startsWith("data: ")) continue;
    const eventData = line.slice(6);
    return { event: "research_run", data: eventData };
  }
  return null;
}
