# Architecture Diagram: Conversations Filter Feature

## Component Hierarchy and Data Flow

```
App Router Structure
====================

Root Layout (Server Component)
├── (dashboard) Layout Group
│   └── conversations/ Layout [THIS IS WHERE 'use client' STARTS]
│       ├── DashboardContext.Provider (value={filters, updateFilter, resetFilters})
│       │
│       ├── /page.tsx (Server Component)
│       │   ├── IdeationQueueHeader
│       │   │   ├── FilterToggleButton (drafts)
│       │   │   │   └── onClick → updateFilter('drafts', ...)
│       │   │   ├── FilterToggleButton (published)
│       │   │   │   └── onClick → updateFilter('published', ...)
│       │   │   └── FilterToggleButton (archived)
│       │   │       └── onClick → updateFilter('archived', ...)
│       │   │
│       │   └── ConversationsList
│       │       ├── useEffect([filters]) → fetch with filters
│       │       └── Renders conversation items
│       │
│       └── /[id]/page.tsx (Server Component)
│           └── Detailed conversation view
│               (filter state preserved from layout)
```

## Data Flow Diagram

```
User Interaction Flow
=====================

1. User clicks "Drafts" toggle button
   ↓
2. FilterToggleButton.onClick() fires
   ↓
3. Calls updateFilter('drafts', !filters.drafts)
   ↓
4. setState in conversations/layout.tsx
   ↓
5. Layout re-renders with new context value
   ↓
6. All context consumers re-render:
   - IdeationQueueHeader (shows active state)
   - ConversationsList (via useEffect)
   ↓
7. ConversationsList useEffect triggers
   ↓
8. Calls getConversations({drafts: true, ...})
   ↓
9. API returns filtered conversations
   ↓
10. ConversationsList renders updated list

State Persistence on Navigation
================================

Before Navigation:
  Layout state: { drafts: true, published: false, archived: false }

User navigates to /conversations/123
  ↓
Layout does NOT re-render (key feature of App Router!)
  ↓
[id]/page.tsx renders
  ↓
Layout state still intact: { drafts: true, published: false, archived: false }
  ↓
User navigates back to /conversations
  ↓
Same layout, same state still there!
```

## State Management Architecture

```
React State in conversations/layout.tsx
=======================================

const [filters, setFilters] = useState({
  archived: false,
  drafts: true,
  published: true,
})

       ↓

DashboardContext.Provider
  ├── value.filters
  ├── value.updateFilter
  └── value.resetFilters

       ↓

Child Components
  ├── IdeationQueueHeader
  │   └── useDashboardContext()
  │       ├── Reads: filters
  │       └── Calls: updateFilter()
  │
  └── ConversationsList
      └── useDashboardContext()
          ├── Reads: filters
          └── Uses in useEffect dependency
```

## Context Flow Diagram

```
Type Definitions
================

ConversationFilters
├── archived?: boolean
├── drafts?: boolean
├── published?: boolean
└── [key: string]: boolean | undefined

       ↓

DashboardContextType
├── filters: ConversationFilters
├── updateFilter: (key: string, value: boolean) => void
└── resetFilters: () => void

       ↓

DashboardContext
└── createContext<DashboardContextType | undefined>()

       ↓

useDashboardContext() Hook
└── Returns DashboardContextType (or throws error)

       ↓

Consumer Components
├── useDashboardContext()
├── Destructure: { filters, updateFilter }
└── Use safely with type checking
```

## File Structure with Dependencies

```
frontend/src/
│
├── features/
│   ├── dashboard/
│   │   └── contexts/
│   │       └── DashboardContext.tsx
│   │           ├── Exports: ConversationFilters
│   │           ├── Exports: DashboardContextType
│   │           ├── Exports: DashboardContext
│   │           └── Exports: useDashboardContext()
│   │
│   └── conversation/
│       ├── components/
│       │   ├── IdeationQueueHeader.tsx
│       │   │   ├── Imports: useDashboardContext
│       │   │   ├── Uses: filters, updateFilter
│       │   │   └── Renders: FilterToggleButtons
│       │   │
│       │   ├── FilterToggleButton.tsx
│       │   │   ├── Props: label, isActive, onChange
│       │   │   └── Emits: onChange(boolean)
│       │   │
│       │   └── ConversationsList.tsx
│       │       ├── Imports: useDashboardContext
│       │       ├── Uses: filters (in useEffect)
│       │       └── Calls: getConversations(filters)
│       │
│       ├── hooks/
│       │   └── useConversations.ts
│       │       ├── Imports: useDashboardContext
│       │       ├── Uses: filters for queryKey
│       │       └── Returns: useQuery(...)
│       │
│       └── api/
│           └── conversations-api.ts
│               ├── getConversations(filters)
│               └── Builds URLSearchParams from filters
│
└── app/
    └── (dashboard)/
        └── conversations/
            ├── layout.tsx
            │   ├── 'use client' directive
            │   ├── useState for filters
            │   ├── useCallback for callbacks
            │   ├── useMemo for context value
            │   └── Provides DashboardContext
            │
            ├── page.tsx (Server Component)
            │   └── Renders IdeationQueueHeader + ConversationsList
            │
            └── [id]/
                └── page.tsx (Server Component)
                    └── Detailed view (layout state preserved)
```

## React 19 + Next.js 15 Component Boundaries

```
'use client' Boundaries
=======================

conversations/layout.tsx ← 'use client' STARTS HERE
│
├── Client Tree:
│   ├── IdeationQueueHeader (Client)
│   │   └── FilterToggleButton (Client)
│   │
│   └── ConversationsList (Client)
│       └── Conversation Items (Client)
│
└── Server Tree (wrapped by client):
    ├── /page.tsx (Server)
    ├── /[id]/page.tsx (Server)
    └── Other nested routes (Server)

Why this works in Next.js 15:
- Client parent can contain Server children
- Server children can use props from client parent
- Context is established at client boundary
- All descendants can access context
```

## API Integration Flow

```
API Call with Filters
=====================

ConversationsList Component
├── useEffect([filters])
│   ↓
├── Call: getConversations(filters)
│   ├── Input: { drafts: true, published: false, archived: false }
│   ├── Build: URLSearchParams
│   │   └── ?drafts=true&published=false&archived=false
│   ├── Fetch: /api/conversations?...
│   └── Return: Promise<Conversation[]>
│   ↓
├── Receive: Array<Conversation>
│   ↓
└── Render: <ul>{conversations.map(...)}</ul>

Alternative with TanStack Query
================================

useConversations Hook
├── useQuery({
│   ├── queryKey: ['conversations', filters]
│   │   └── Re-run if filters change
│   ├── queryFn: () => getConversations(filters)
│   │   └── Only runs when queryKey changes
│   └── staleTime: 5 min
│       └── Cache results
│
└── Return: { data, isLoading, error }

Component Usage
└── const { data: conversations } = useConversations()
```

## State Updates Sequence Diagram

```
Toggle Button Click
===================

1. User clicks toggle
   │
   └─ <button onClick={() => updateFilter('drafts', !filters.drafts)}>
      │
      └─ IdeationQueueHeader component
         │
         └─ useDashboardContext() hook
            │
            └─ Calls: updateFilter('drafts', false)

2. updateFilter executes in layout
   │
   └─ setFilters(prev => ({...prev, 'drafts': false}))
      │
      └─ Layout state updated
         │
         └─ React schedules re-render

3. Layout re-renders
   │
   └─ const contextValue = useMemo(
         () => ({filters, updateFilter, resetFilters}),
         [...deps]
      )
      │
      └─ New context value created

4. DashboardContext.Provider updated
   │
   └─ All consumers notified
      │
      ├─ IdeationQueueHeader
      │  └─ Re-renders with new filters
      │     └─ Button shows active state
      │
      └─ ConversationsList
         └─ Re-renders
            └─ useEffect triggers (filters in dependency array)
               └─ Calls getConversations(newFilters)
                  └─ Fetches new data
                     └─ Re-renders with new conversations
```

## Performance Optimization Points

```
Optimization Techniques
=======================

1. useMemo for Context Value
   const contextValue = useMemo(
     () => ({ filters, updateFilter, resetFilters }),
     [filters, updateFilter, resetFilters]
   )
   └─ Prevents unnecessary re-renders of consumers

2. useCallback for Callbacks
   const updateFilter = useCallback(
     (key, value) => setFilters(...),
     []  // No dependencies - always same reference
   )
   └─ Stable callback reference

3. useEffect with Dependency Array
   useEffect(() => {
     fetchConversations()
   }, [filters])  // Only run when filters change
   └─ Don't fetch if filters haven't changed

4. TanStack Query Cache
   queryKey: ['conversations', filters]
   staleTime: 5 * 60 * 1000
   └─ Caches results, reuses within 5 minutes

5. App Router Layout Preservation
   └─ Layout doesn't re-render on navigation
      └─ Filter state persists for free
```

## Comparison: With vs Without Proper Architecture

```
❌ WRONG APPROACH
=================

conversations/page.tsx (Server Component)
  ├── [State in page component]
  └── Only works for this page
      └── State lost when navigating

Child pages can't access filter state!

---

✅ CORRECT APPROACH (This Feature)
===================================

conversations/layout.tsx (Client Component with state)
  ├── [State in layout]
  ├── Provides via context
  └── Works for all child pages
      ├── /conversations/page.tsx can access
      ├── /conversations/[id]/page.tsx can access
      └── /conversations/new/page.tsx can access

State persists across navigation!
```

## Testing Flow

```
Test Checklist
==============

1. Filter Toggle Test
   User clicks "Drafts"
   ↓
   Verify button shows active state
   ↓
   Verify ConversationsList re-renders
   ↓
   Verify API call includes drafts=true

2. API Integration Test
   Set filters to { drafts: true, published: false }
   ↓
   Check Network tab in DevTools
   ↓
   Verify URL: /api/conversations?drafts=true
   ↓
   Verify results show only drafts

3. State Persistence Test
   Set filters
   ↓
   Navigate to /conversations/123
   ↓
   Filters still active
   ↓
   Navigate back to /conversations
   ↓
   Filters still same

4. Performance Test
   Open React DevTools Profiler
   ↓
   Click toggle
   ↓
   Verify only necessary components re-render
   ↓
   IdeationQueueHeader ✓
   ↓
   ConversationsList ✓
   ↓
   Other components ✗ (shouldn't re-render)

5. Type Safety Test
   Try wrong argument: updateFilter('drafts', 'yes')
   ↓
   Should get TypeScript error
   ↓
   Correct: updateFilter('drafts', true)
   ↓
   Should compile
```

## Next.js 15 vs Next.js 14 Differences

```
Next.js 14
==========
- App Router available
- Layout state reset on navigation
- Manual context management

Next.js 15 (This Project)
=========================
- App Router default
- Layout state PRESERVED on navigation ← Key difference!
- Better Server Component support
- React 19 integration
- Improved caching with fetch()

This feature leverages Next.js 15's layout state preservation!
```

## Summary Architecture

```
┌─────────────────────────────────────────────┐
│  conversations/layout.tsx ('use client')    │
│  ├─ useState: filters                       │
│  ├─ useCallback: updateFilter, resetFilters│
│  ├─ useMemo: contextValue                   │
│  └─ Provider: DashboardContext              │
└──────────────┬────────────────────────────┘
               │
               ├─ Provides: { filters, updateFilter, resetFilters }
               │
        ┌──────┴──────┬──────────┐
        │             │          │
        ▼             ▼          ▼
   Header      Content      Sidebar
 (IdeationQ)  (Conversations)(Future)
      │             │
      ├─ Buttons    ├─ useEffect
      │             ├─ Fetch with filters
      └─ Toggle     └─ Render list
        state
        change
        │
        └─ updateFilter()
           └─ setState
              └─ Re-render
                 └─ Context updated
                    └─ API call made
                       └─ Results shown
```

This architecture ensures:
- ✅ Filter state persists across navigation
- ✅ Type-safe context usage
- ✅ Optimized re-renders
- ✅ Clean separation of concerns
- ✅ React 19 + Next.js 15 best practices
