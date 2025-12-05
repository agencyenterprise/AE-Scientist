# Next.js Technical Guidance

## Agent
nextjs-expert

## Timestamp
2025-12-03 21:30

## Project Analysis

### Detected Versions
| Package | Version | Notes |
|---------|---------|-------|
| next | 15.4.7 | App Router, Turbopack enabled for dev |
| react | 19.1.0 | Server Components, `use` hook available |
| react-dom | 19.1.0 | |
| typescript | ^5 | |
| @tanstack/react-query | ^5.90.10 | Server state management |
| zustand | ^5.0.8 | Client state management |
| tailwindcss | ^4 | v4 syntax |

### Router Type
**App Router** - The project uses `next dev --turbopack` and App Router conventions.

### Key Configuration
- Turbopack enabled for development (`next dev --turbopack`)
- React 19 with full Server Components support
- Feature-based architecture under `src/features/`
- Shared utilities under `src/shared/`

---

## React 19 + Next.js 15 Considerations

### 1. React Compiler Status (Important Context)

The **React Compiler is now stable** and production-tested at Meta. However, it's a separate tool from React 19 itself and requires explicit opt-in. Key points:

- **Automatic memoization**: When enabled, the compiler auto-memoizes components, hooks, and values
- **Current recommendation**: Continue using `useCallback`/`useMemo` for now, but don't over-optimize
- **Future-proofing**: Write code following Rules of React; the compiler will optimize it when adopted

**For this refactoring**: Continue using `useCallback` for callbacks passed to effects or memoized children. The existing patterns in the codebase are correct.

### 2. No Changes to Core Hook APIs

React 19 did NOT change the core APIs for `useState`, `useEffect`, `useCallback`, `useMemo`, or `useRef`. The patterns in your existing hooks remain valid.

New React 19 features like `use()`, `useActionState`, and `useOptimistic` are **not relevant** to this SSE/streaming refactoring since:
- SSE connections are client-only (browser API)
- The `use()` hook is for consuming promises passed from Server Components
- Your streaming hooks manage imperative connections, not declarative data fetching

### 3. Server vs Client Component Boundaries

All the hooks being refactored are **Client Component hooks** (they use browser APIs like `fetch`, `AbortController`, `EventSource`). This is correct and unchanged in Next.js 15.

```typescript
// Correct: Client-only hooks must be in 'use client' files or imported into client components
// Your hooks already follow this pattern - no changes needed
```

---

## Version-Specific Patterns for This Refactoring

### Pattern 1: AbortController Cleanup in useEffect

**Current best practice** - your existing code follows this correctly:

```typescript
// RECOMMENDED PATTERN (your hooks already use this)
useEffect(() => {
  const controller = new AbortController();

  async function connect() {
    try {
      const response = await fetch(url, { signal: controller.signal });
      // ... handle response
    } catch (error) {
      if ((error as Error).name === 'AbortError') {
        return; // Expected on unmount - don't report as error
      }
      // Handle actual errors
    }
  }

  connect();

  return () => {
    controller.abort();
  };
}, [dependencies]);
```

**Key points:**
- Create `AbortController` inside the effect, not outside
- Check for `AbortError` in catch block to distinguish from real errors
- Clean up in the return function, not in a separate cleanup effect

### Pattern 2: useCallback for Event Handlers in SSE Hooks

When callbacks are passed to effects or used as effect dependencies, wrap them in `useCallback`:

```typescript
// CORRECT: Memoize callbacks that are effect dependencies
const handleEvent = useCallback((event: SSEEvent) => {
  switch (event.type) {
    case 'log': onLog(event.data as LogEntry); break;
    // ...
  }
}, [onLog, onStageProgress, /* other callbacks */]);

useEffect(() => {
  // Use handleEvent in effect
}, [handleEvent, /* other deps */]);
```

**When to use useCallback:**
- When the function is a dependency of `useEffect`
- When passing to memoized child components
- When returning from custom hooks (allows consumers to optimize)

**When NOT needed:**
- Event handlers passed directly to DOM elements (`onClick={handleClick}`)
- Functions only used inside the component render

### Pattern 3: Ref Pattern for Mutable Values

For values that need to persist across renders without triggering re-renders:

```typescript
// CORRECT: Use refs for mutable values that don't need to trigger re-renders
const abortControllerRef = useRef<AbortController | null>(null);
const reconnectTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
const reconnectAttemptsRef = useRef(0);

// Access .current without triggering re-renders
reconnectAttemptsRef.current++;
```

### Pattern 4: Callback Refs for Multiple Cleanup Concerns

When you need to track multiple mutable values that require cleanup:

```typescript
// CORRECT: Keep cleanup logic close to the resource creation
const connect = useCallback(async () => {
  // Cleanup previous connection
  if (abortControllerRef.current) {
    abortControllerRef.current.abort();
  }
  if (reconnectTimeoutRef.current) {
    clearTimeout(reconnectTimeoutRef.current);
  }

  // Create new connection
  const controller = new AbortController();
  abortControllerRef.current = controller;

  // ... connection logic
}, [dependencies]);
```

---

## Hook Composition Best Practices (React 19)

### Pattern: Facade Hook with Sub-Hooks

This is the recommended pattern for your refactoring:

```typescript
// Sub-hook: Single responsibility
function useImportFormState() {
  const [url, setUrl] = useState('');
  const [error, setError] = useState('');

  const validate = useCallback(() => {
    if (!validateUrl(url)) {
      setError(getUrlValidationError());
      return false;
    }
    return true;
  }, [url]);

  const reset = useCallback(() => {
    setUrl('');
    setError('');
  }, []);

  return {
    state: { url, error },
    actions: { setUrl, setError, validate, reset }
  };
}

// Facade hook: Composes sub-hooks, maintains original API
function useConversationImport(options: Options) {
  const formState = useImportFormState();
  const conflictState = useImportConflictResolution();
  const streaming = useStreamingImport({
    onSuccess: options.onSuccess,
    // ...
  });

  // Compose actions that span multiple concerns
  const startImport = useCallback(async () => {
    if (!formState.actions.validate()) return;
    await streaming.actions.startStream({
      url: formState.state.url,
      // ...
    });
  }, [formState, streaming]);

  // Return original API shape for backward compatibility
  return {
    state: {
      url: formState.state.url,
      error: formState.state.error,
      streamingContent: streaming.state.streamingContent,
      // ...
    },
    actions: {
      setUrl: formState.actions.setUrl,
      startImport,
      // ...
    }
  };
}
```

**Benefits:**
- Each sub-hook is independently testable
- Consumers can import sub-hooks directly for granular access
- Original API preserved for backward compatibility
- Clear separation of concerns

### Anti-Pattern: Avoid Deep Callback Chains

```typescript
// AVOID: Callbacks that wrap callbacks
const handleSuccess = useCallback(() => {
  const innerCallback = useCallback(() => { // Wrong: hook inside callback
    // ...
  }, []);
}, []);

// CORRECT: Define all callbacks at the top level
const innerCallback = useCallback(() => { /* ... */ }, []);
const handleSuccess = useCallback(() => {
  innerCallback();
}, [innerCallback]);
```

---

## useSSEStream Implementation Guidance

### Core Pattern for Generic SSE Hook

```typescript
// shared/hooks/use-sse-stream.ts
'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import { apiStream } from '@/shared/lib/api-client';

export interface SSEStreamOptions<TEvent> {
  url: string;
  method?: 'GET' | 'POST';
  body?: object;
  enabled: boolean;
  parseEvent: (line: string) => TEvent | null;
  onEvent: (event: TEvent) => void;
  onComplete?: () => void;
  onError?: (error: string) => void;
  delimiter?: string;
  reconnect?: boolean;
  maxReconnectAttempts?: number;
}

export interface SSEStreamReturn {
  isConnected: boolean;
  connectionError: string | null;
  reconnect: () => void;
  disconnect: () => void;
}

export function useSSEStream<TEvent>(
  options: SSEStreamOptions<TEvent>
): SSEStreamReturn {
  const {
    url,
    method = 'GET',
    body,
    enabled,
    parseEvent,
    onEvent,
    onComplete,
    onError,
    delimiter = '\n',
    reconnect: shouldReconnect = false,
    maxReconnectAttempts = 5,
  } = options;

  const [isConnected, setIsConnected] = useState(false);
  const [connectionError, setConnectionError] = useState<string | null>(null);

  // Refs for cleanup and reconnection
  const abortControllerRef = useRef<AbortController | null>(null);
  const reconnectTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const reconnectAttemptsRef = useRef(0);

  // Cleanup helper
  const cleanup = useCallback(() => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      abortControllerRef.current = null;
    }
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
      reconnectTimeoutRef.current = null;
    }
  }, []);

  const connect = useCallback(async () => {
    if (!enabled) return;

    // Cleanup previous connection
    cleanup();

    const controller = new AbortController();
    abortControllerRef.current = controller;

    try {
      const response = await apiStream(url, {
        method,
        body: body ? JSON.stringify(body) : undefined,
        headers: { Accept: 'text/event-stream' },
        signal: controller.signal,
      });

      if (!response.body) {
        throw new Error('No response body');
      }

      setIsConnected(true);
      setConnectionError(null);
      reconnectAttemptsRef.current = 0;

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split(delimiter);
        buffer = lines.pop() || '';

        for (const line of lines) {
          if (!line.trim()) continue;

          const event = parseEvent(line);
          if (event) {
            onEvent(event);
          }
        }
      }

      // Stream completed normally
      setIsConnected(false);
      onComplete?.();

    } catch (error) {
      if ((error as Error).name === 'AbortError') {
        return; // Expected on cleanup
      }

      setIsConnected(false);
      const errorMessage = error instanceof Error ? error.message : 'Connection failed';
      setConnectionError(errorMessage);

      // Handle reconnection
      if (shouldReconnect && reconnectAttemptsRef.current < maxReconnectAttempts) {
        const delay = Math.min(1000 * Math.pow(2, reconnectAttemptsRef.current), 30000);
        reconnectAttemptsRef.current++;
        reconnectTimeoutRef.current = setTimeout(connect, delay);
      } else if (shouldReconnect) {
        onError?.('Max reconnection attempts reached');
      } else {
        onError?.(errorMessage);
      }
    }
  }, [
    enabled,
    url,
    method,
    body,
    delimiter,
    parseEvent,
    onEvent,
    onComplete,
    onError,
    shouldReconnect,
    maxReconnectAttempts,
    cleanup,
  ]);

  // Connect on mount/enable, cleanup on unmount/disable
  useEffect(() => {
    if (enabled) {
      connect();
    }
    return cleanup;
  }, [enabled, connect, cleanup]);

  const disconnect = useCallback(() => {
    cleanup();
    setIsConnected(false);
  }, [cleanup]);

  return {
    isConnected,
    connectionError,
    reconnect: connect,
    disconnect,
  };
}
```

### Key Implementation Notes

1. **Why `apiStream` instead of raw `fetch`**: Your existing `api-client.ts` handles:
   - 401 redirects to login
   - Base URL configuration
   - Consistent error handling
   - HTTP->HTTPS upgrades on Railway

2. **Buffer management**: The pattern `buffer = lines.pop() || ''` handles partial lines correctly. The last element after split may be an incomplete line.

3. **Delimiter handling**: Different endpoints use different delimiters:
   - Import: `\n` (JSON per line)
   - Research: `\n\n` (SSE format with `data: ` prefix)

4. **Reconnection with exponential backoff**: `Math.min(1000 * Math.pow(2, attempts), 30000)` caps at 30 seconds.

---

## StringSection Component Guidance

### Variant-Based Styling Pattern

```typescript
// features/project-draft/components/StringSection.tsx
import { cva, type VariantProps } from 'class-variance-authority';
import { cn } from '@/shared/lib/utils';

const sectionVariants = cva(
  // Base styles
  'relative group',
  {
    variants: {
      variant: {
        default: '',
        'primary-border': 'border-l-4 border-primary pl-4',
        'success-box': 'bg-green-50 dark:bg-green-950/20 rounded-lg p-4',
      },
    },
    defaultVariants: {
      variant: 'default',
    },
  }
);

const contentVariants = cva(
  'prose prose-sm dark:prose-invert max-w-none',
  {
    variants: {
      variant: {
        default: 'text-foreground/90',
        'primary-border': 'text-foreground',
        'success-box': 'text-foreground',
      },
    },
    defaultVariants: {
      variant: 'default',
    },
  }
);

interface StringSectionProps extends VariantProps<typeof sectionVariants> {
  title: string;
  content: string;
  diffContent?: React.ReactElement[] | null;
  onEdit?: () => void;
  className?: string;
}

export function StringSection({
  title,
  content,
  diffContent,
  onEdit,
  variant,
  className,
}: StringSectionProps) {
  return (
    <div className={cn(sectionVariants({ variant }), className)}>
      <div className="flex items-center justify-between mb-2">
        <h3 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
          {title}
        </h3>
        {onEdit && (
          <button
            onClick={onEdit}
            className="opacity-0 group-hover:opacity-100 transition-opacity"
            aria-label={`Edit ${title}`}
          >
            <Pencil className="h-4 w-4" />
          </button>
        )}
      </div>
      <div className={cn(contentVariants({ variant }))}>
        {diffContent ? (
          diffContent
        ) : (
          <ReactMarkdown components={markdownComponents}>
            {content}
          </ReactMarkdown>
        )}
      </div>
    </div>
  );
}
```

**Why `class-variance-authority`:**
- Already in your dependencies (used by shadcn/ui)
- Type-safe variants
- Composable with `cn()` utility
- Clear mapping between variant name and styles

---

## Common Pitfalls to Avoid

### 1. Stale Closures in Callbacks

```typescript
// WRONG: onEvent might have stale references
const onEvent = (event) => {
  setSomeState(prev => [...prev, event]); // OK - using function update
  doSomething(someValue); // WRONG - someValue might be stale
};

// CORRECT: Include dependencies or use refs
const someValueRef = useRef(someValue);
someValueRef.current = someValue;

const onEvent = useCallback((event) => {
  doSomething(someValueRef.current);
}, []); // Stable reference, current value via ref
```

### 2. Missing AbortError Check

```typescript
// WRONG: Logs error on expected unmount
catch (error) {
  console.error('Connection failed:', error);
}

// CORRECT: Distinguish abort from real errors
catch (error) {
  if ((error as Error).name === 'AbortError') {
    return; // Expected on unmount
  }
  console.error('Connection failed:', error);
}
```

### 3. Effect Dependency Exhaustiveness

```typescript
// WRONG: Missing dependencies cause bugs
useEffect(() => {
  if (enabled && url) {
    connect();
  }
}, [enabled]); // Missing `url` and `connect`

// CORRECT: Include all dependencies
useEffect(() => {
  if (enabled && url) {
    connect();
  }
}, [enabled, url, connect]);
```

### 4. Reconnection Timer Cleanup

```typescript
// WRONG: Timer continues after unmount
reconnectTimeoutRef.current = setTimeout(connect, delay);

// CORRECT: Always clean up timers
return () => {
  if (reconnectTimeoutRef.current) {
    clearTimeout(reconnectTimeoutRef.current);
  }
};
```

---

## Testing Recommendations

### Hook Testing with Mocked Streams

```typescript
// Use MSW or similar to mock SSE endpoints
import { setupServer } from 'msw/node';
import { http, HttpResponse } from 'msw';

const server = setupServer(
  http.get('/api/stream', () => {
    const stream = new ReadableStream({
      start(controller) {
        controller.enqueue('{"type":"log","data":"test"}\n');
        controller.close();
      },
    });
    return new HttpResponse(stream, {
      headers: { 'Content-Type': 'text/event-stream' },
    });
  })
);

// Test hook behavior
describe('useSSEStream', () => {
  it('parses events correctly', async () => {
    const onEvent = vi.fn();
    const { result } = renderHook(() => useSSEStream({
      url: '/api/stream',
      enabled: true,
      parseEvent: (line) => JSON.parse(line),
      onEvent,
    }));

    await waitFor(() => {
      expect(onEvent).toHaveBeenCalledWith({ type: 'log', data: 'test' });
    });
  });
});
```

---

## Documentation References

- [React useCallback](https://react.dev/reference/react/useCallback) - Official useCallback documentation
- [React Compiler Introduction](https://react.dev/learn/react-compiler/introduction) - Compiler status and automatic memoization
- [Next.js Server and Client Components](https://nextjs.org/docs/app/getting-started/server-and-client-components) - Component boundaries
- [Understanding useEffect Cleanup](https://blog.logrocket.com/understanding-react-useeffect-cleanup-function/) - Cleanup patterns
- [AbortController in React](https://www.j-labs.pl/en/tech-blog/how-to-use-the-useeffect-hook-with-the-abortcontroller/) - AbortController patterns
- [Advanced React Hooks 2025](https://dev.to/tahamjp/advanced-react-hooks-in-2025-patterns-you-should-know-2e4n) - Modern hook patterns

---

## For Executor: Key Points Summary

1. **No API changes needed** - React 19 and Next.js 15 don't change the hook patterns you're using. The existing code follows correct patterns.

2. **AbortController is the right choice** - Continue using `AbortController` for SSE cleanup. This is the recommended pattern for cancelable async operations.

3. **useCallback usage is correct** - Your current use of `useCallback` for callbacks passed to effects is appropriate. The React Compiler will optimize this when adopted, but the code is correct now.

4. **Facade pattern is clean** - The proposed hook composition pattern aligns with React best practices for separating concerns while maintaining backward compatibility.

5. **Use apiStream from api-client** - The existing `apiStream` utility handles auth redirects and base URL, so use it instead of raw `fetch` in the new `useSSEStream` hook.

6. **Buffer management pattern** - The `buffer = lines.pop() || ''` pattern correctly handles partial SSE lines. Keep this in the generic hook.

7. **Exponential backoff for reconnection** - The pattern in `useResearchRunSSE` (1s, 2s, 4s, 8s, 16s, capped at 30s) is correct. Extract it to the generic hook.

8. **class-variance-authority for StringSection** - Use CVA for the variant prop since it's already in the project (via shadcn/ui) and provides type-safe styling.
