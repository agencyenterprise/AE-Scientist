# SOP: Frontend API Hooks

## Related Documentation
- [Frontend Architecture](../System/frontend_architecture.md)
- [Project Architecture](../System/project_architecture.md)

---

## Overview

This SOP covers creating custom React hooks for API calls in the frontend. Use this procedure when you need to:
- Fetch data from the backend API
- Handle loading and error states
- Implement caching and debouncing
- Create reusable data fetching logic

---

## Prerequisites

- Node.js environment set up
- Understanding of React hooks (useState, useCallback, useRef, useMemo)
- Knowledge of the API endpoints you're integrating

---

## Step-by-Step Procedure

### 1. Define Types

```typescript
// frontend/src/types/myFeature.ts
export interface MyFeatureItem {
  id: string
  name: string
  description: string
  createdAt: string
}

export interface MyFeatureListResponse {
  items: MyFeatureItem[]
  total: number
  page: number
  pageSize: number
}

export interface MyFeatureState {
  items: MyFeatureItem[]
  total: number
  loading: boolean
  error: string | null
}
```

### 2. Create the Hook

```typescript
// frontend/src/hooks/useMyFeature.ts
import { useState, useCallback, useRef, useMemo } from "react"
import { config } from "@/lib/config"
import type {
  MyFeatureItem,
  MyFeatureListResponse,
  MyFeatureState
} from "@/types/myFeature"

interface UseMyFeatureReturn {
  // State
  state: MyFeatureState

  // Actions
  fetchItems: (page?: number) => Promise<void>
  createItem: (data: Omit<MyFeatureItem, "id" | "createdAt">) => Promise<MyFeatureItem>
  updateItem: (id: string, data: Partial<MyFeatureItem>) => Promise<MyFeatureItem>
  deleteItem: (id: string) => Promise<void>
  refresh: () => Promise<void>

  // Utilities
  getItemById: (id: string) => MyFeatureItem | undefined
  clearError: () => void
}

export function useMyFeature(): UseMyFeatureReturn {
  // State
  const [state, setState] = useState<MyFeatureState>({
    items: [],
    total: 0,
    loading: false,
    error: null
  })

  // Cache for avoiding duplicate requests
  const cacheRef = useRef<Map<string, MyFeatureItem[]>>(new Map())
  const currentPageRef = useRef(1)

  // Fetch items with pagination
  const fetchItems = useCallback(async (page = 1) => {
    setState(prev => ({ ...prev, loading: true, error: null }))
    currentPageRef.current = page

    try {
      const response = await fetch(
        `${config.apiUrl}/my-feature?page=${page}&pageSize=25`,
        { credentials: "include" }
      )

      if (!response.ok) {
        throw new Error(`Failed to fetch: ${response.status}`)
      }

      const data: MyFeatureListResponse = await response.json()

      setState(prev => ({
        ...prev,
        items: data.items,
        total: data.total,
        loading: false
      }))

      // Cache the results
      cacheRef.current.set(`page-${page}`, data.items)
    } catch (error) {
      const message = error instanceof Error ? error.message : "Unknown error"
      setState(prev => ({
        ...prev,
        loading: false,
        error: message
      }))
    }
  }, [])

  // Create new item
  const createItem = useCallback(async (
    data: Omit<MyFeatureItem, "id" | "createdAt">
  ): Promise<MyFeatureItem> => {
    const response = await fetch(`${config.apiUrl}/my-feature`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      credentials: "include",
      body: JSON.stringify(data)
    })

    if (!response.ok) {
      throw new Error(`Failed to create: ${response.status}`)
    }

    const created: MyFeatureItem = await response.json()

    // Update state with new item
    setState(prev => ({
      ...prev,
      items: [created, ...prev.items],
      total: prev.total + 1
    }))

    // Clear cache
    cacheRef.current.clear()

    return created
  }, [])

  // Update existing item
  const updateItem = useCallback(async (
    id: string,
    data: Partial<MyFeatureItem>
  ): Promise<MyFeatureItem> => {
    const response = await fetch(`${config.apiUrl}/my-feature/${id}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      credentials: "include",
      body: JSON.stringify(data)
    })

    if (!response.ok) {
      throw new Error(`Failed to update: ${response.status}`)
    }

    const updated: MyFeatureItem = await response.json()

    // Update state
    setState(prev => ({
      ...prev,
      items: prev.items.map(item =>
        item.id === id ? updated : item
      )
    }))

    // Clear cache
    cacheRef.current.clear()

    return updated
  }, [])

  // Delete item
  const deleteItem = useCallback(async (id: string): Promise<void> => {
    const response = await fetch(`${config.apiUrl}/my-feature/${id}`, {
      method: "DELETE",
      credentials: "include"
    })

    if (!response.ok) {
      throw new Error(`Failed to delete: ${response.status}`)
    }

    // Update state
    setState(prev => ({
      ...prev,
      items: prev.items.filter(item => item.id !== id),
      total: prev.total - 1
    }))

    // Clear cache
    cacheRef.current.clear()
  }, [])

  // Refresh current page
  const refresh = useCallback(async () => {
    cacheRef.current.clear()
    await fetchItems(currentPageRef.current)
  }, [fetchItems])

  // Get item by ID from current state
  const getItemById = useCallback((id: string): MyFeatureItem | undefined => {
    return state.items.find(item => item.id === id)
  }, [state.items])

  // Clear error
  const clearError = useCallback(() => {
    setState(prev => ({ ...prev, error: null }))
  }, [])

  // Memoize return value
  return useMemo(() => ({
    state,
    fetchItems,
    createItem,
    updateItem,
    deleteItem,
    refresh,
    getItemById,
    clearError
  }), [
    state,
    fetchItems,
    createItem,
    updateItem,
    deleteItem,
    refresh,
    getItemById,
    clearError
  ])
}
```

### 3. Add Debouncing (for Search)

```typescript
// frontend/src/hooks/useMyFeatureSearch.ts
import { useState, useCallback, useRef, useMemo } from "react"
import { config } from "@/lib/config"

interface UseMyFeatureSearchReturn {
  query: string
  results: MyFeatureItem[]
  loading: boolean
  error: string | null
  search: (query: string) => void
  clearSearch: () => void
}

export function useMyFeatureSearch(): UseMyFeatureSearchReturn {
  const [query, setQuery] = useState("")
  const [results, setResults] = useState<MyFeatureItem[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // Debounce timer ref
  const debounceRef = useRef<NodeJS.Timeout | null>(null)

  // Search with debouncing
  const search = useCallback((searchQuery: string) => {
    setQuery(searchQuery)

    // Clear previous timer
    if (debounceRef.current) {
      clearTimeout(debounceRef.current)
    }

    // Don't search for empty queries
    if (!searchQuery.trim()) {
      setResults([])
      return
    }

    // Debounce the API call
    debounceRef.current = setTimeout(async () => {
      setLoading(true)
      setError(null)

      try {
        const response = await fetch(
          `${config.apiUrl}/my-feature/search?q=${encodeURIComponent(searchQuery)}`,
          { credentials: "include" }
        )

        if (!response.ok) {
          throw new Error("Search failed")
        }

        const data = await response.json()
        setResults(data.items)
      } catch (err) {
        setError(err instanceof Error ? err.message : "Search error")
        setResults([])
      } finally {
        setLoading(false)
      }
    }, 300) // 300ms debounce
  }, [])

  // Clear search
  const clearSearch = useCallback(() => {
    if (debounceRef.current) {
      clearTimeout(debounceRef.current)
    }
    setQuery("")
    setResults([])
    setError(null)
  }, [])

  return useMemo(() => ({
    query,
    results,
    loading,
    error,
    search,
    clearSearch
  }), [query, results, loading, error, search, clearSearch])
}
```

### 4. Use the Hook in a Component

```typescript
// frontend/src/components/MyFeatureList.tsx
"use client"

import { useEffect } from "react"
import { useMyFeature } from "@/hooks/useMyFeature"

export function MyFeatureList() {
  const {
    state: { items, loading, error },
    fetchItems,
    deleteItem,
    refresh
  } = useMyFeature()

  useEffect(() => {
    fetchItems()
  }, [fetchItems])

  if (loading) {
    return <div>Loading...</div>
  }

  if (error) {
    return (
      <div className="text-red-500">
        Error: {error}
        <button onClick={refresh}>Retry</button>
      </div>
    )
  }

  return (
    <ul className="space-y-2">
      {items.map(item => (
        <li key={item.id} className="flex justify-between p-2 border rounded">
          <span>{item.name}</span>
          <button
            onClick={() => deleteItem(item.id)}
            className="text-red-500"
          >
            Delete
          </button>
        </li>
      ))}
    </ul>
  )
}
```

---

## Key Files

| File | Purpose |
|------|---------|
| `src/features/[feature]/hooks/` | Feature-specific hooks |
| `src/shared/hooks/useAuth.ts` | Authentication hook |
| `src/shared/hooks/useSearch.ts` | Search hook with debouncing |
| `src/shared/providers/QueryProvider.tsx` | React Query configuration |
| `src/shared/lib/config.ts` | API configuration |
| `src/shared/lib/api-adapters.ts` | Anti-corruption layer for API responses |
| `src/types/api.gen.ts` | Auto-generated OpenAPI types |

---

## Hook Return Pattern

```typescript
interface UseHookReturn {
  // State (read-only)
  state: StateType
  // or individual state values:
  items: Item[]
  loading: boolean
  error: string | null

  // Actions (mutations)
  fetch: () => Promise<void>
  create: (data: CreateData) => Promise<Item>
  update: (id: string, data: UpdateData) => Promise<Item>
  delete: (id: string) => Promise<void>

  // Utilities (helpers)
  getById: (id: string) => Item | undefined
  validate: (data: Data) => boolean
  clear: () => void
}
```

---

## Common Patterns

### API Call with Credentials

```typescript
const response = await fetch(`${config.apiUrl}/endpoint`, {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  credentials: "include", // Required for auth cookies
  body: JSON.stringify(data)
})
```

### Error Response Handling

```typescript
interface ErrorResponse {
  detail: string
}

function isErrorResponse(data: unknown): data is ErrorResponse {
  return (
    typeof data === "object" &&
    data !== null &&
    "detail" in data
  )
}

// Usage
if (!response.ok) {
  const data = await response.json()
  if (isErrorResponse(data)) {
    throw new Error(data.detail)
  }
  throw new Error(`Request failed: ${response.status}`)
}
```

### Caching with useRef

```typescript
const cacheRef = useRef<Map<string, Data>>(new Map())

const fetchWithCache = useCallback(async (key: string) => {
  // Check cache first
  if (cacheRef.current.has(key)) {
    return cacheRef.current.get(key)
  }

  // Fetch from API
  const data = await fetchData(key)

  // Store in cache
  cacheRef.current.set(key, data)

  return data
}, [])
```

---

## Common Pitfalls

- **Always use `useCallback`**: Prevents unnecessary re-renders
- **Always use `useMemo` for return value**: Maintains referential equality
- **Include `credentials: "include"`**: Required for authentication
- **Handle all error states**: Check `response.ok` before parsing JSON
- **Clear cache on mutations**: Invalidate cache after create/update/delete
- **Use `useRef` for mutable values**: Timers, caches, previous values
- **Don't call hooks conditionally**: Follow Rules of Hooks

---

## Verification

1. Test the hook in isolation:
   ```typescript
   const { state, fetchItems } = useMyFeature()
   useEffect(() => { fetchItems() }, [fetchItems])
   console.log(state)
   ```

2. Verify loading states appear correctly

3. Test error handling by simulating API errors

4. Check caching works (no duplicate requests)

5. Verify debouncing for search hooks (network tab)

6. Test mutations update state correctly

---

## React Query Integration

The frontend uses React Query for server state management via `QueryProvider`.

### When to Use React Query vs useState/useEffect

> Added from: research-history-home implementation (2025-12-03)

**Use React Query (`useQuery`) when:**
- Fetching read-only data from an API endpoint
- Data should be cached and potentially shared across components
- You want automatic background refetching on window focus
- You need loading, error, and success states managed automatically
- The component may mount/unmount frequently (caching prevents refetch)

**Use useState/useEffect when:**
- Managing purely local UI state (no API)
- One-time data transformations
- Side effects that aren't data fetching
- Highly custom streaming scenarios (though `useSSEStream` is preferred)

**Example - Simple Data Fetch (Recommended: React Query)**:

```typescript
// RECOMMENDED: React Query
import { useQuery } from "@tanstack/react-query";
import { apiFetch } from "@/shared/lib/api-client";

export function useRecentItems() {
  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ["recent-items"],
    queryFn: () => apiFetch<ItemsResponse>("/items/?limit=10"),
    staleTime: 30 * 1000, // 30 seconds
  });

  return {
    items: data?.items ?? [],
    isLoading,
    error: error instanceof Error ? error.message : null,
    refetch,
  };
}
```

```typescript
// AVOID: useState/useEffect for simple fetches
// This pattern misses caching, deduplication, and standardized error handling
import { useState, useEffect, useCallback } from "react";

export function useRecentItems() {
  const [items, setItems] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);

  const fetchItems = useCallback(async () => {
    setIsLoading(true);
    try {
      const data = await apiFetch("/items/?limit=10");
      setItems(data.items);
    } catch (err) {
      setError(err.message);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchItems();
  }, [fetchItems]);

  return { items, isLoading, error, refetch: fetchItems };
}
```

### Stale Time Recommendations

| Use Case | Stale Time | Rationale |
|----------|------------|-----------|
| Frequently changing data (home page feeds) | 30 seconds | Balance freshness vs performance |
| Configuration/settings | 5 minutes | Rarely changes during session |
| User profile | 1 minute | Moderate update frequency |
| Search results | 0 (default) | Always fresh for new searches |
| Nested/expandable data (runs, sub-items) | 30 seconds | User expects updates when re-expanding |

### On-Demand Nested Data Fetching

> Added from: ideation-queue-research-runs implementation (2025-12-08)

When fetching data for nested/expandable UI elements, use conditional rendering instead of React Query's `enabled` flag. This pattern is cleaner and aligns with React's mental model.

**Pattern: Conditional Render (Recommended)**

```typescript
// In parent component
const [isExpanded, setIsExpanded] = useState(false);

return (
  <div>
    <button onClick={() => setIsExpanded(prev => !prev)}>Toggle</button>
    {/* Component only mounts when expanded, triggering the fetch */}
    {isExpanded && <NestedDataList itemId={id} />}
  </div>
);

// In NestedDataList component
export function NestedDataList({ itemId }: { itemId: number }) {
  // Hook runs unconditionally when component is mounted
  const { data, isLoading, error, refetch } = useNestedData(itemId);

  if (isLoading) return <Skeleton />;
  if (error) return <ErrorWithRetry onRetry={refetch} />;
  return <DataList items={data} />;
}

// In hook - no enabled flag needed
export function useNestedData(itemId: number) {
  return useQuery({
    queryKey: ["nested-data", itemId],
    queryFn: () => fetchNestedData(itemId),
    staleTime: 30 * 1000,  // 30 seconds
    gcTime: 5 * 60 * 1000, // 5 minutes - keep in cache after unmount
  });
}
```

**Why this is better than `enabled` flag:**

1. Hook is only instantiated when needed (no wasted query subscriptions)
2. Matches React's mental model (mount = fetch, unmount = cleanup)
3. React Query cache persists data between mount/unmount cycles
4. No need to track expanded state in the hook

**When to use `enabled` flag instead:**

- When the hook is called unconditionally but you want to skip the fetch
- When you need to access the query client before data is needed
- When the hook is part of a larger composition that can't be conditionally rendered

**Type Derivation for Nested API Data**

When extracting types from nested API response fields:

```typescript
import type { ConversationResponse } from "@/types";

// Derive the array item type from the response
type ResearchRunSummary = NonNullable<ConversationResponse["research_runs"]>[number];

async function fetchNestedData(id: number): Promise<ResearchRunSummary[]> {
  const data = await apiFetch<ConversationResponse>(`/conversations/${id}`);
  // Sort by created_at descending (newest first)
  return (data.research_runs ?? []).sort(
    (a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
  );
}
```

This approach:
- Derives types directly from auto-generated API schema
- Ensures type safety aligned with backend
- Automatically updates when API schema changes
- Avoids manual type duplication

### QueryProvider Configuration

```typescript
// shared/providers/QueryProvider.tsx
"use client"

import { QueryClient, QueryClientProvider } from "@tanstack/react-query"

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 60 * 1000, // 1 minute
      refetchOnWindowFocus: false,
    },
  },
})

export function QueryProvider({ children }: { children: React.ReactNode }) {
  return (
    <QueryClientProvider client={queryClient}>
      {children}
    </QueryClientProvider>
  )
}
```

### Using React Query in Hooks

```typescript
// features/conversation/hooks/useConversations.ts
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import { config } from "@/shared/lib/config"

export function useConversations() {
  return useQuery({
    queryKey: ["conversations"],
    queryFn: async () => {
      const response = await fetch(`${config.apiUrl}/conversations`, {
        credentials: "include",
      })
      if (!response.ok) throw new Error("Failed to fetch")
      return response.json()
    },
  })
}

export function useDeleteConversation() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: async (id: string) => {
      const response = await fetch(`${config.apiUrl}/conversations/${id}`, {
        method: "DELETE",
        credentials: "include",
      })
      if (!response.ok) throw new Error("Failed to delete")
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["conversations"] })
    },
  })
}
```

---

## Streaming Hook Pattern

> Updated from: frontend-solid-refactoring implementation (2025-12-03)

For Server-Sent Events (SSE) streaming responses, use the shared `useSSEStream` hook:

### Using the Generic SSE Hook

```typescript
// features/my-feature/hooks/useMyFeatureStream.ts
import { useCallback } from "react"
import { useSSEStream } from "@/shared/hooks/use-sse-stream"

interface MyEvent {
  type: 'data' | 'status' | 'complete'
  data: unknown
}

export function useMyFeatureStream(
  conversationId: number,
  onData: (data: unknown) => void,
  onStatus: (status: string) => void
) {
  // Parser function converts raw SSE lines to typed events
  const parseEvent = useCallback((line: string): MyEvent | null => {
    if (!line.trim()) return null
    try {
      return JSON.parse(line) as MyEvent
    } catch {
      console.warn("Failed to parse SSE line:", line)
      return null
    }
  }, [])

  // Handler dispatches events to appropriate callbacks
  const handleEvent = useCallback((event: MyEvent) => {
    switch (event.type) {
      case 'data':
        onData(event.data)
        break
      case 'status':
        onStatus(event.data as string)
        break
    }
  }, [onData, onStatus])

  return useSSEStream({
    url: `/conversations/${conversationId}/stream`,
    enabled: true,
    parseEvent,
    onEvent: handleEvent,
    onComplete: () => console.log("Stream complete"),
    onError: (error) => console.error("Stream error:", error),
    delimiter: '\n',        // '\n' for JSON lines, '\n\n' for SSE format
    reconnect: true,        // auto-reconnect on failure
    maxReconnectAttempts: 5,
  })
}
```

### For SSE with `data: ` Prefix

Some endpoints use the standard SSE format with `data: ` prefix:

```typescript
const parseEvent = useCallback((line: string) => {
  // Handle SSE format: "data: {...}"
  if (!line.startsWith('data: ')) return null
  const jsonStr = line.slice(6) // Remove "data: " prefix
  return JSON.parse(jsonStr)
}, [])

// Use with '\n\n' delimiter for SSE format
return useSSEStream({
  url: `/api/events`,
  parseEvent,
  delimiter: '\n\n',  // SSE uses double newline
  // ...
})
```

### For Import Streaming

Use `useStreamingImport` for conversation/idea import operations:

```typescript
import { useStreamingImport } from "@/shared/hooks/use-streaming-import"

export function useMyImport(options: { onSuccess?: (id: number) => void }) {
  const { state, actions, streamingRef } = useStreamingImport({
    onSuccess: options.onSuccess,
    onError: (error) => toast.error(error),
  })

  const startImport = async (url: string, model: string, provider: string) => {
    await actions.startStream({
      url,
      model,
      provider,
      duplicateResolution: 'prompt',
    })
  }

  return {
    ...state,
    startImport,
    reset: actions.reset,
    streamingRef,
  }
}
```

### Legacy Pattern (Direct Implementation)

For simple streaming without the shared hook:

```typescript
// features/project-draft/hooks/useChatStreaming.ts
import { useState, useCallback, useRef } from "react"
import { config } from "@/shared/lib/config"

interface UseChatStreamingReturn {
  isStreaming: boolean
  streamMessage: (message: string) => Promise<void>
  cancelStream: () => void
}

export function useChatStreaming(
  onChunk: (chunk: string) => void,
  onComplete: () => void
): UseChatStreamingReturn {
  const [isStreaming, setIsStreaming] = useState(false)
  const abortControllerRef = useRef<AbortController | null>(null)

  const streamMessage = useCallback(async (message: string) => {
    setIsStreaming(true)
    abortControllerRef.current = new AbortController()

    try {
      const response = await fetch(`${config.apiUrl}/chat/stream`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({ message }),
        signal: abortControllerRef.current.signal,
      })

      if (!response.ok) throw new Error("Stream request failed")

      const reader = response.body?.getReader()
      const decoder = new TextDecoder()

      if (!reader) throw new Error("No response body")

      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        const chunk = decoder.decode(value, { stream: true })
        onChunk(chunk)
      }

      onComplete()
    } catch (error) {
      if ((error as Error).name !== "AbortError") {
        console.error("Streaming error:", error)
      }
    } finally {
      setIsStreaming(false)
    }
  }, [onChunk, onComplete])

  const cancelStream = useCallback(() => {
    abortControllerRef.current?.abort()
    setIsStreaming(false)
  }, [])

  return { isStreaming, streamMessage, cancelStream }
}
```

---

## S3 Artifact Download Pattern

> Added from: frontend-final-pdf-banner implementation (2025-12-04)

For downloading files from S3 with authentication/authorization validation, use the presigned URL pattern. This avoids CORS and browser redirect handling issues.

### Problem Solved
HTTP 307 redirects to presigned S3 URLs can fail with AccessDenied errors due to browser handling and CORS issues. The solution is to return the presigned URL as JSON, then redirect the browser directly.

### Implementation Pattern

**Backend Endpoint** (returns presigned URL as JSON):
```python
# server/app/api/my_feature.py
from app.models import ArtifactPresignedUrlResponse

@router.get("/{artifact_id}/presign")
def get_artifact_presigned_url(
    artifact_id: int,
    request: Request
) -> ArtifactPresignedUrlResponse:
    user = get_current_user(request)

    # Validate ownership/access
    artifact = db.get_artifact(artifact_id)
    if not artifact or artifact.user_id != user.id:
        raise HTTPException(status_code=404, detail="Artifact not found")

    # Generate presigned URL using existing S3 service
    s3 = get_s3_service()
    download_url = s3.generate_download_url(artifact.s3_key, expires_in=3600)

    return ArtifactPresignedUrlResponse(
        url=download_url,
        expires_in=3600,
        artifact_id=artifact_id,
        filename=artifact.filename
    )
```

**Frontend Hook** (fetches URL and redirects):
```typescript
// features/my-feature/hooks/useArtifactDownload.ts
import { useState } from "react";
import { apiFetch } from "@/shared/lib/api-client";

interface ArtifactPresignedUrlResponse {
  url: string;
  expires_in: number;
  artifact_id: number;
  filename: string;
}

interface UseArtifactDownloadReturn {
  downloadArtifact: (artifactId: number) => Promise<void>;
  isDownloading: boolean;
  downloadingArtifactId: number | null;  // For per-item loading states
  error: string | null;
}

export function useArtifactDownload(baseUrl: string): UseArtifactDownloadReturn {
  const [isDownloading, setIsDownloading] = useState(false);
  const [downloadingArtifactId, setDownloadingArtifactId] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);

  const downloadArtifact = async (artifactId: number) => {
    setIsDownloading(true);
    setDownloadingArtifactId(artifactId);
    setError(null);

    try {
      // Fetch presigned URL from backend
      const response = await apiFetch<ArtifactPresignedUrlResponse>(
        `${baseUrl}/${artifactId}/presign`
      );

      // Redirect browser to presigned URL (triggers download)
      window.location.href = response.url;
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to download");
    } finally {
      setIsDownloading(false);
      setDownloadingArtifactId(null);
    }
  };

  return { downloadArtifact, isDownloading, downloadingArtifactId, error };
}
```

**Component Usage** (button with loading state):
```typescript
function ArtifactsList({ artifacts, baseUrl }) {
  const { downloadArtifact, isDownloading, downloadingArtifactId, error } =
    useArtifactDownload(baseUrl);

  return (
    <ul>
      {artifacts.map(artifact => (
        <li key={artifact.id}>
          <span>{artifact.filename}</span>
          <button
            onClick={() => downloadArtifact(artifact.id)}
            disabled={isDownloading}
          >
            {downloadingArtifactId === artifact.id ? (
              <span>Downloading...</span>
            ) : (
              <span>Download</span>
            )}
          </button>
        </li>
      ))}
      {error && <div className="text-red-500">{error}</div>}
    </ul>
  );
}
```

### When to Use

- Downloading files from S3 that require authentication
- User-initiated downloads (not background fetches)
- When you need ownership/access validation before providing the URL
- Avoiding CORS issues with redirect-based downloads

### Key Points

1. **Use button, not anchor link**: The download is async (needs API call first)
2. **Track artifact ID**: Enables per-item loading indicators in lists
3. **Disable all during download**: Prevents concurrent downloads
4. **Show error in UI**: Don't fail silently
5. **Use `window.location.href`**: Triggers browser's native download handling

---

## Context-Based Hook Pattern

For shared state across components using React Context:

```typescript
// features/conversation/hooks/useConversationActions.ts
import { useCallback } from "react"
import { useConversation } from "../context/ConversationContext"
import { config } from "@/shared/lib/config"

export function useConversationActions() {
  const { selectedConversation, setSelectedConversation } = useConversation()

  const updateTitle = useCallback(async (newTitle: string) => {
    if (!selectedConversation) return

    const response = await fetch(
      `${config.apiUrl}/conversations/${selectedConversation.id}`,
      {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({ title: newTitle }),
      }
    )

    if (!response.ok) throw new Error("Failed to update")

    const updated = await response.json()
    setSelectedConversation(updated)
    return updated
  }, [selectedConversation, setSelectedConversation])

  const deleteConversation = useCallback(async () => {
    if (!selectedConversation) return

    await fetch(`${config.apiUrl}/conversations/${selectedConversation.id}`, {
      method: "DELETE",
      credentials: "include",
    })

    setSelectedConversation(null)
  }, [selectedConversation, setSelectedConversation])

  return { updateTitle, deleteConversation }
}
