# Next.js 15 Technical Guidance: Conversations Filter Feature

## Agent
nextjs-15-expert

## Timestamp
2025-12-10 12:00 UTC

---

## Project Analysis

### Detected Versions
| Package | Version | Notes |
|---------|---------|-------|
| next | 15.4.8 | App Router (default) |
| react | 19.1.2 | React 19 support |
| typescript | ^5 | Latest TypeScript |
| @tanstack/react-query | ^5.90.10 | Server-side compatible |
| zustand | ^5.0.8 | Lightweight state library |

### Router Type
App Router (default for Next.js 15) with `(dashboard)` route group for layout wrapping.

### Key Configuration
- Dev server uses **Turbopack** (`npm run dev --turbopack`)
- Server-side fetching optimized with `fetch` API caching
- Client-side interactivity via `'use client'` directive

---

## Version-Specific Guidance for Conversations Filter Feature

### Architecture Overview

Your conversations filtering feature requires:
1. **Filter state management** in the layout (shared across all nested routes)
2. **Filter controls** in a child component (interactive buttons)
3. **API calls** that include filter parameters

In **Next.js 15 with React 19**, the optimal pattern is:
- **Layout**: Server Component + Client boundary (`'use client'`) for state
- **Child components**: Can be Server Components that receive state via props
- **Filter toggles**: Client Component for interactive event handlers

---

## 1. Best Pattern for Managing Filter State in Layout.tsx

### The Pattern: Use `'use client'` in Layout for Client Interactivity

```typescript
// frontend/src/app/(dashboard)/conversations/layout.tsx
'use client'

import { useState, useCallback, ReactNode } from 'react'
import { DashboardContext } from '@/features/dashboard/contexts/DashboardContext'

export interface ConversationFilters {
  archived?: boolean
  drafts?: boolean
  published?: boolean
  [key: string]: boolean | undefined
}

interface ConversationLayoutProps {
  children: ReactNode
}

export default function ConversationsLayout({ children }: ConversationLayoutProps) {
  // Filter state
  const [filters, setFilters] = useState<ConversationFilters>({
    archived: false,
    drafts: true,
    published: true,
  })

  // Memoized callback to avoid unnecessary re-renders
  const updateFilter = useCallback((key: string, value: boolean) => {
    setFilters(prev => ({
      ...prev,
      [key]: value,
    }))
  }, [])

  // Reset filters callback
  const resetFilters = useCallback(() => {
    setFilters({
      archived: false,
      drafts: true,
      published: true,
    })
  }, [])

  // Provide context to all child components
  return (
    <DashboardContext.Provider value={{ filters, updateFilter, resetFilters }}>
      <div className="conversations-layout">
        {/* Your layout UI here */}
        {children}
      </div>
    </DashboardContext.Provider>
  )
}
```

### Key Points for Next.js 15 + React 19:

- **`'use client'` at top**: Marks this as a Client Component. All imports become part of client bundle.
- **`useState` in layout**: Persists filter state across navigation between child pages.
- **`useCallback` for callbacks**: Optimizes re-renders of context consumers (required with React 19's strict memoization).
- **Context Provider**: Wraps children to provide state to all descendant components.

### Why This Works with App Router:

> "On navigation, layouts preserve state, remain interactive, and do not rerender."

This means:
- Filter state persists when navigating between `/conversations`, `/conversations/[id]`, etc.
- Layout doesn't re-render on child page navigation
- Child pages always see current filter state

---

## 2. Properly Typing the Context with Filter Callbacks

### Define the Context Interface

```typescript
// frontend/src/features/dashboard/contexts/DashboardContext.tsx
'use client'

import { createContext, useContext } from 'react'

// Type for filter state
export interface ConversationFilters {
  archived?: boolean
  drafts?: boolean
  published?: boolean
  [key: string]: boolean | undefined
}

// Type for context value
export interface DashboardContextType {
  // State
  filters: ConversationFilters

  // Callbacks
  updateFilter: (key: string, value: boolean) => void
  resetFilters: () => void
}

// Create context with undefined default (will be provided by layout)
const DashboardContext = createContext<DashboardContextType | undefined>(undefined)

export { DashboardContext }

// Custom hook for consuming context (recommended pattern)
export function useDashboardContext(): DashboardContextType {
  const context = useContext(DashboardContext)

  if (!context) {
    throw new Error('useDashboardContext must be used within DashboardContext.Provider')
  }

  return context
}
```

### Consuming the Context in Child Components

```typescript
// frontend/src/features/conversation/components/IdeationQueueHeader.tsx
'use client'

import { useDashboardContext } from '@/features/dashboard/contexts/DashboardContext'

export function IdeationQueueHeader() {
  const { filters, updateFilter } = useDashboardContext()

  return (
    <header className="ideation-queue-header">
      <div className="filter-toggles">
        <button
          className={`toggle-btn ${filters.drafts ? 'active' : ''}`}
          onClick={() => updateFilter('drafts', !filters.drafts)}
          aria-pressed={filters.drafts}
        >
          Drafts
        </button>

        <button
          className={`toggle-btn ${filters.published ? 'active' : ''}`}
          onClick={() => updateFilter('published', !filters.published)}
          aria-pressed={filters.published}
        >
          Published
        </button>

        <button
          className={`toggle-btn ${filters.archived ? 'active' : ''}`}
          onClick={() => updateFilter('archived', !filters.archived)}
          aria-pressed={filters.archived}
        >
          Archived
        </button>
      </div>
    </header>
  )
}
```

### Key TypeScript Patterns for React 19:

1. **Explicit Context Type**: `DashboardContextType` ensures type safety.
2. **Custom Hook Pattern** (`useDashboardContext`): Encapsulates context access with error handling.
3. **Arrow Function Callbacks**: `updateFilter` and `resetFilters` use arrow functions for stable references.
4. **Optional Properties**: `filters[key]?: boolean` allows flexible filter additions.

---

## 3. React 19 Considerations for Toggle Button Handlers

### Event Handlers in React 19

React 19 has subtle changes to event handling. Here's the correct pattern:

```typescript
// React 19: Click handlers work as before, but with better type inference
<button
  onClick={() => updateFilter('drafts', !filters.drafts)}
  type="button"
  aria-pressed={filters.drafts}
  className={clsx(
    'px-4 py-2 rounded border-2 transition-colors',
    filters.drafts
      ? 'border-blue-500 bg-blue-50 text-blue-700'
      : 'border-gray-300 bg-white text-gray-600 hover:border-gray-400'
  )}
>
  Drafts
</button>
```

### Important React 19 Notes:

1. **Event Delegation**: React still uses event delegation (automatically optimized by React 19).
2. **Stable Callbacks**: Use `useCallback` if handlers are passed as props to avoid re-renders.
3. **No Handler Warnings**: React 19 improved error messages for missing required handlers.

### Complete Toggle Button Component with Proper Typing

```typescript
// frontend/src/features/conversation/components/FilterToggleButton.tsx
'use client'

import { PropsWithChildren } from 'react'
import clsx from 'clsx'

interface FilterToggleButtonProps extends PropsWithChildren {
  label: string
  isActive: boolean
  onChange: (value: boolean) => void
  testId?: string
}

export function FilterToggleButton({
  label,
  isActive,
  onChange,
  testId,
  children,
}: FilterToggleButtonProps) {
  return (
    <button
      type="button"
      data-testid={testId}
      onClick={() => onChange(!isActive)}
      aria-pressed={isActive}
      className={clsx(
        'px-4 py-2 rounded border-2 font-medium transition-all duration-200',
        isActive
          ? 'border-blue-500 bg-blue-50 text-blue-700 shadow-sm'
          : 'border-gray-300 bg-white text-gray-600 hover:border-gray-400'
      )}
    >
      {children || label}
    </button>
  )
}
```

---

## 4. URL Query Parameters for Bookmarkable Filters (Optional, Recommended)

### Option A: Use `useRouter` and `useSearchParams` (Client Component)

If you want filters to be bookmarkable/shareable:

```typescript
// frontend/src/features/conversation/components/IdeationQueueHeader.tsx
'use client'

import { useRouter, useSearchParams } from 'next/navigation'
import { useCallback } from 'react'
import { useDashboardContext } from '@/features/dashboard/contexts/DashboardContext'

export function IdeationQueueHeader() {
  const router = useRouter()
  const searchParams = useSearchParams()
  const { filters, updateFilter } = useDashboardContext()

  const handleFilterChange = useCallback((key: string, value: boolean) => {
    // Update local state
    updateFilter(key, value)

    // Update URL
    const params = new URLSearchParams(searchParams)
    if (value) {
      params.set(key, 'true')
    } else {
      params.delete(key)
    }

    router.push(`?${params.toString()}`, { scroll: false })
  }, [updateFilter, router, searchParams])

  return (
    <header className="ideation-queue-header">
      <div className="filter-toggles">
        <button
          onClick={() => handleFilterChange('drafts', !filters.drafts)}
          aria-pressed={filters.drafts}
        >
          Drafts
        </button>
        {/* ... more filters ... */}
      </div>
    </header>
  )
}
```

### Option B: Initialize Filters from URL (Recommended)

```typescript
// frontend/src/app/(dashboard)/conversations/layout.tsx
'use client'

import { useSearchParams } from 'next/navigation'
import { useState, useCallback, useEffect, ReactNode } from 'react'
import { DashboardContext } from '@/features/dashboard/contexts/DashboardContext'

export interface ConversationFilters {
  archived?: boolean
  drafts?: boolean
  published?: boolean
}

export default function ConversationsLayout({ children }: { children: ReactNode }) {
  const searchParams = useSearchParams()

  // Initialize from URL or defaults
  const [filters, setFilters] = useState<ConversationFilters>(() => ({
    archived: searchParams.get('archived') === 'true',
    drafts: searchParams.get('drafts') !== 'false', // Default true
    published: searchParams.get('published') !== 'false', // Default true
  }))

  const updateFilter = useCallback((key: string, value: boolean) => {
    setFilters(prev => ({
      ...prev,
      [key]: value,
    }))
  }, [])

  const resetFilters = useCallback(() => {
    setFilters({
      archived: false,
      drafts: true,
      published: true,
    })
  }, [])

  return (
    <DashboardContext.Provider value={{ filters, updateFilter, resetFilters }}>
      <div className="conversations-layout">
        {children}
      </div>
    </DashboardContext.Provider>
  )
}
```

### Why This Pattern Works:

1. **Bookmarkable**: Users can share filtered URLs
2. **Browser Back/Forward**: Works automatically with `useRouter`
3. **Sync'd State**: Local state and URL stay in sync
4. **Server-Friendly**: URL params can be read in Server Components via `params`

---

## Data Fetching: Passing Filters to API Calls

### Option 1: Server Component Child with Filters Prop

```typescript
// frontend/src/app/(dashboard)/conversations/page.tsx
// Server Component that receives filters via context

import { ConversationsList } from '@/features/conversation/components/ConversationsList'

export default function ConversationsPage() {
  return <ConversationsList />
}
```

```typescript
// frontend/src/features/conversation/components/ConversationsList.tsx
'use client'

import { useEffect } from 'react'
import { useDashboardContext } from '@/features/dashboard/contexts/DashboardContext'
import { getConversations } from '@/features/conversation/api/conversations-api'

export function ConversationsList() {
  const { filters } = useDashboardContext()

  useEffect(() => {
    const fetchConversations = async () => {
      const response = await getConversations({
        archived: filters.archived,
        drafts: filters.drafts,
        published: filters.published,
      })
      // Update your state with results
    }

    fetchConversations()
  }, [filters]) // Re-fetch when filters change

  // Render conversations...
  return <div>Conversations...</div>
}
```

### Option 2: TanStack Query Integration (Recommended)

```typescript
// frontend/src/features/conversation/hooks/useConversations.ts
'use client'

import { useQuery } from '@tanstack/react-query'
import { useDashboardContext } from '@/features/dashboard/contexts/DashboardContext'
import { getConversations } from '@/features/conversation/api/conversations-api'

export function useConversations() {
  const { filters } = useDashboardContext()

  return useQuery({
    queryKey: ['conversations', filters], // Query invalidates when filters change
    queryFn: () => getConversations(filters),
    staleTime: 1000 * 60 * 5, // 5 minutes
  })
}
```

---

## Do's and Don'ts for Next.js 15 + React 19

### Do's ✅

1. **Use `'use client'` only in the layout** (or filter toggle component) - not in the entire page
2. **Use `useCallback`** for callbacks passed to context - React 19 strictly memoizes dependencies
3. **Await `params` and `searchParams`** - They are Promises in Next.js 15 (if using Server Components)
4. **Use custom hooks** like `useDashboardContext` to encapsulate context logic
5. **Leverage `useSearchParams`** and `useRouter` for bookmarkable filters
6. **Implement `aria-pressed`** on toggle buttons for accessibility
7. **Use TypeScript interfaces** for context and filter state - type safety with React 19 is stricter

### Don'ts ❌

1. **Don't wrap everything in `'use client'`** - Keep Server Components as default
2. **Don't recreate context providers on every render** - Use `useMemo` or `useCallback`
3. **Don't forget about React.memo** for context consumers - Can help with performance
4. **Don't use inline object literals** as context values - Always memoize with `useMemo`
5. **Don't mix useState in Server Components** - Use only in Client Components
6. **Don't ignore the callback dependencies** in `useCallback` - React 19 is stricter about closures

### Gotcha: Context with Layout State

In Next.js App Router:
- Layout **preserves state** on navigation
- This is different from Pages Router where navigating would re-render the layout
- Ensure your context provider is memoized to prevent unnecessary re-renders

```typescript
// Good: Memoize context value
const contextValue = useMemo(
  () => ({ filters, updateFilter, resetFilters }),
  [filters, updateFilter, resetFilters]
)

return (
  <DashboardContext.Provider value={contextValue}>
    {children}
  </DashboardContext.Provider>
)

// This prevents child components from re-rendering when context provider re-renders
```

---

## File Structure Recommendation

```
frontend/src/
├── app/
│   └── (dashboard)/
│       └── conversations/
│           ├── layout.tsx              # 'use client' - State management
│           ├── page.tsx                # Server Component - Main content
│           └── [id]/
│               └── page.tsx            # Individual conversation page
│
├── features/
│   ├── conversation/
│   │   ├── components/
│   │   │   ├── IdeationQueueHeader.tsx # 'use client' - Filter controls
│   │   │   ├── FilterToggleButton.tsx  # 'use client' - Reusable button
│   │   │   └── ConversationsList.tsx   # 'use client' - Uses context
│   │   ├── hooks/
│   │   │   └── useConversations.ts     # TanStack Query hook
│   │   ├── api/
│   │   │   └── conversations-api.ts    # API calls
│   │   └── types/
│   │       └── conversation.types.ts   # TypeScript types
│   │
│   └── dashboard/
│       └── contexts/
│           └── DashboardContext.tsx    # 'use client' - Context definition
```

---

## Documentation References

**Next.js 15 Official Documentation:**
- Getting Started: https://nextjs.org/docs/15/app/getting-started
- Server & Client Components: https://nextjs.org/docs/15/app/getting-started/server-and-client-components
- Data Fetching: https://nextjs.org/docs/15/app/getting-started/fetching-data
- Layouts & Pages: https://nextjs.org/docs/15/app/getting-started/layouts-and-pages
- Linking & Navigation: https://nextjs.org/docs/15/app/getting-started/linking-and-navigating
- Error Handling: https://nextjs.org/docs/15/app/getting-started/error-handling

**React 19 Key Changes:**
- Automatic batching improved
- Server Components enhanced
- Improved form handling
- Built-in error boundaries

**TanStack Query Documentation:**
- https://tanstack.com/query/latest
- Perfect for managing server state with filter parameters

---

## Summary of Key Patterns

### 1. Layout State Management
```typescript
'use client'
// Use useState in layout, provide via context
```

### 2. Context Type Safety
```typescript
interface DashboardContextType {
  filters: ConversationFilters
  updateFilter: (key: string, value: boolean) => void
  resetFilters: () => void
}
```

### 3. Toggle Button with Event Handler
```typescript
onClick={() => updateFilter('drafts', !filters.drafts)}
```

### 4. Bookmarkable Filters (Optional)
```typescript
useSearchParams() // Read current filter state
useRouter().push(`?${params.toString()}`) // Update URL
```

### 5. API Integration with Filters
```typescript
useQuery({
  queryKey: ['conversations', filters], // Re-fetch on filter change
  queryFn: () => getConversations(filters),
})
```

---

## Next Steps for Executor

When implementing, follow this order:

1. **Create DashboardContext** with proper TypeScript types
2. **Update conversations/layout.tsx** with state management and context provider
3. **Create FilterToggleButton** component for reusability
4. **Update IdeationQueueHeader** to use context and handle filter changes
5. **Add filter parameters to API calls** (getConversations)
6. **(Optional) Add URL query params** for bookmarkable filters
7. **Test** filter state persistence on navigation
8. **Performance test** - Check React DevTools Profiler to ensure no unnecessary re-renders

---

## Questions & Clarifications

This guidance covers:
- ✅ Best pattern for filter state in layout
- ✅ Proper context typing with callbacks
- ✅ React 19 event handler considerations
- ✅ Optional URL query param pattern
- ✅ API integration with filters
- ✅ Common gotchas and best practices

If clarification is needed during implementation, refer back to the specific sections above.
