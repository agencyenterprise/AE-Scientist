# Next.js 15 Quick Reference: Conversations Filter Implementation

## Quick Copy-Paste Code Snippets

### 1. DashboardContext Definition

**File:** `frontend/src/features/dashboard/contexts/DashboardContext.tsx`

```typescript
'use client'

import { createContext, useContext } from 'react'

export interface ConversationFilters {
  archived?: boolean
  drafts?: boolean
  published?: boolean
  [key: string]: boolean | undefined
}

export interface DashboardContextType {
  filters: ConversationFilters
  updateFilter: (key: string, value: boolean) => void
  resetFilters: () => void
}

export const DashboardContext = createContext<DashboardContextType | undefined>(undefined)

export function useDashboardContext(): DashboardContextType {
  const context = useContext(DashboardContext)
  if (!context) {
    throw new Error('useDashboardContext must be used within DashboardContext.Provider')
  }
  return context
}
```

---

### 2. Conversations Layout with State

**File:** `frontend/src/app/(dashboard)/conversations/layout.tsx`

```typescript
'use client'

import { useState, useCallback, ReactNode, useMemo } from 'react'
import { DashboardContext, ConversationFilters } from '@/features/dashboard/contexts/DashboardContext'

interface ConversationLayoutProps {
  children: ReactNode
}

export default function ConversationsLayout({ children }: ConversationLayoutProps) {
  const [filters, setFilters] = useState<ConversationFilters>({
    archived: false,
    drafts: true,
    published: true,
  })

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

  // Memoize context value to prevent unnecessary re-renders
  const contextValue = useMemo(
    () => ({ filters, updateFilter, resetFilters }),
    [filters, updateFilter, resetFilters]
  )

  return (
    <DashboardContext.Provider value={contextValue}>
      <div className="conversations-layout">
        {children}
      </div>
    </DashboardContext.Provider>
  )
}
```

---

### 3. Filter Toggle Button Component

**File:** `frontend/src/features/conversation/components/FilterToggleButton.tsx`

```typescript
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

### 4. Updated IdeationQueueHeader

**File:** `frontend/src/features/conversation/components/IdeationQueueHeader.tsx`

```typescript
'use client'

import { useDashboardContext } from '@/features/dashboard/contexts/DashboardContext'
import { FilterToggleButton } from './FilterToggleButton'

export function IdeationQueueHeader() {
  const { filters, updateFilter } = useDashboardContext()

  return (
    <header className="ideation-queue-header flex items-center justify-between p-4 border-b">
      <h1 className="text-2xl font-bold">Conversations</h1>

      <div className="flex gap-2">
        <FilterToggleButton
          label="Drafts"
          isActive={filters.drafts ?? false}
          onChange={(value) => updateFilter('drafts', value)}
          testId="filter-drafts"
        />

        <FilterToggleButton
          label="Published"
          isActive={filters.published ?? false}
          onChange={(value) => updateFilter('published', value)}
          testId="filter-published"
        />

        <FilterToggleButton
          label="Archived"
          isActive={filters.archived ?? false}
          onChange={(value) => updateFilter('archived', value)}
          testId="filter-archived"
        />
      </div>
    </header>
  )
}
```

---

### 5. Conversations Page (Server Component)

**File:** `frontend/src/app/(dashboard)/conversations/page.tsx`

```typescript
// Server Component - No 'use client' needed
import { ConversationsList } from '@/features/conversation/components/ConversationsList'
import { IdeationQueueHeader } from '@/features/conversation/components/IdeationQueueHeader'

export default function ConversationsPage() {
  return (
    <div>
      <IdeationQueueHeader />
      <ConversationsList />
    </div>
  )
}
```

---

### 6. ConversationsList Component (with Filters)

**File:** `frontend/src/features/conversation/components/ConversationsList.tsx`

```typescript
'use client'

import { useEffect } from 'react'
import { useDashboardContext } from '@/features/dashboard/contexts/DashboardContext'
import { getConversations } from '@/features/conversation/api/conversations-api'

export function ConversationsList() {
  const { filters } = useDashboardContext()

  useEffect(() => {
    const fetchConversations = async () => {
      try {
        const response = await getConversations({
          archived: filters.archived,
          drafts: filters.drafts,
          published: filters.published,
        })
        // Handle response - update local state or query client
        console.log('Conversations:', response)
      } catch (error) {
        console.error('Failed to fetch conversations:', error)
      }
    }

    fetchConversations()
  }, [filters]) // Re-fetch when filters change

  return (
    <div className="conversations-list">
      {/* Render your conversations list */}
    </div>
  )
}
```

---

### 7. API Hook (TanStack Query)

**File:** `frontend/src/features/conversation/hooks/useConversations.ts`

```typescript
'use client'

import { useQuery } from '@tanstack/react-query'
import { useDashboardContext } from '@/features/dashboard/contexts/DashboardContext'
import { getConversations } from '@/features/conversation/api/conversations-api'

export function useConversations() {
  const { filters } = useDashboardContext()

  return useQuery({
    queryKey: ['conversations', filters],
    queryFn: () =>
      getConversations({
        archived: filters.archived,
        drafts: filters.drafts,
        published: filters.published,
      }),
    staleTime: 1000 * 60 * 5, // 5 minutes
  })
}
```

---

### 8. API Function

**File:** `frontend/src/features/conversation/api/conversations-api.ts`

```typescript
import { ConversationFilters } from '@/features/dashboard/contexts/DashboardContext'

export interface Conversation {
  id: string
  title: string
  status: 'draft' | 'published' | 'archived'
  createdAt: string
  updatedAt: string
}

export async function getConversations(filters: ConversationFilters) {
  const params = new URLSearchParams()

  // Only add filter params if they're set to true
  if (filters.drafts) params.append('status', 'draft')
  if (filters.published) params.append('status', 'published')
  if (filters.archived) params.append('status', 'archived')

  const response = await fetch(`/api/conversations?${params.toString()}`, {
    method: 'GET',
    headers: {
      'Content-Type': 'application/json',
    },
  })

  if (!response.ok) {
    throw new Error('Failed to fetch conversations')
  }

  return response.json() as Promise<Conversation[]>
}
```

---

## Implementation Checklist

- [ ] Create `DashboardContext.tsx` with types and custom hook
- [ ] Update `conversations/layout.tsx` with state and context provider
- [ ] Create `FilterToggleButton.tsx` component
- [ ] Update `IdeationQueueHeader.tsx` to use context
- [ ] Create or update `ConversationsList.tsx` to use filters
- [ ] Create `useConversations.ts` hook (if using TanStack Query)
- [ ] Update/create conversations API functions
- [ ] Test filter state persistence on navigation
- [ ] Test filter changes trigger API calls
- [ ] Verify no console errors or warnings
- [ ] Performance: Check React DevTools Profiler

---

## Common Issues & Solutions

### Issue: "useDashboardContext must be used within DashboardContext.Provider"

**Solution**: Make sure your layout is wrapping children with DashboardContext.Provider

```typescript
return (
  <DashboardContext.Provider value={contextValue}>
    {children}
  </DashboardContext.Provider>
)
```

### Issue: Filters reset when navigating

**Solution**: This shouldn't happen with App Router. If it does, check:
1. Layout has `'use client'` at top
2. Context provider wraps `children`
3. State is in layout, not individual pages

### Issue: Unnecessary re-renders when filters change

**Solution**: Memoize the context value using `useMemo`:

```typescript
const contextValue = useMemo(
  () => ({ filters, updateFilter, resetFilters }),
  [filters, updateFilter, resetFilters]
)
```

### Issue: TypeScript errors with context

**Solution**: Ensure context is properly typed:

```typescript
export interface DashboardContextType {
  filters: ConversationFilters
  updateFilter: (key: string, value: boolean) => void
  resetFilters: () => void
}

const context = useContext(DashboardContext) // Properly typed!
```

---

## React 19 + Next.js 15 Key Reminders

1. **`'use client'` marks component boundary** - All children become client components
2. **Layouts preserve state** on navigation (unlike Pages Router)
3. **`useCallback` is important** - React 19 strictly checks dependencies
4. **`params` and `searchParams` are Promises** in Server Components
5. **Always provide default types** for context to avoid undefined errors
6. **Memoize context values** to prevent unnecessary re-renders

---

## Files to Create/Update

```
frontend/src/
├── features/
│   ├── dashboard/
│   │   └── contexts/
│   │       └── DashboardContext.tsx          # CREATE
│   │
│   └── conversation/
│       ├── components/
│       │   ├── IdeationQueueHeader.tsx       # UPDATE
│       │   ├── FilterToggleButton.tsx        # CREATE
│       │   └── ConversationsList.tsx         # CREATE/UPDATE
│       ├── hooks/
│       │   └── useConversations.ts           # CREATE (optional)
│       └── api/
│           └── conversations-api.ts          # CREATE/UPDATE
│
└── app/
    └── (dashboard)/
        └── conversations/
            ├── layout.tsx                    # UPDATE
            └── page.tsx                      # CREATE/UPDATE
```

---

## Next.js 15 Specific Features Used

- **App Router** - Modern routing with layouts
- **Client Components** - Interactive state management
- **Server Components** - Static content rendering
- **Context API** - State sharing without prop drilling
- **useCallback** - Optimized callback references
- **useMemo** - Memoized context values
- **React 19** - Enhanced component composition

All patterns follow Next.js 15.4.8 best practices with React 19.1.2.
