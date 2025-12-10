# Next.js 15 Q&A: Conversations Filter Feature

## Your Specific Questions Answered

---

## Q1: Best pattern for managing filter state in layout.tsx with "use client"?

### Answer

The optimal pattern is:

**Layout with `'use client'` directive + Context Provider:**

```typescript
// frontend/src/app/(dashboard)/conversations/layout.tsx
'use client'

import { useState, useCallback, ReactNode, useMemo } from 'react'
import { DashboardContext } from '@/features/dashboard/contexts/DashboardContext'

export default function ConversationsLayout({ children }: { children: ReactNode }) {
  const [filters, setFilters] = useState({
    archived: false,
    drafts: true,
    published: true,
  })

  const updateFilter = useCallback((key: string, value: boolean) => {
    setFilters(prev => ({ ...prev, [key]: value }))
  }, [])

  const resetFilters = useCallback(() => {
    setFilters({ archived: false, drafts: true, published: true })
  }, [])

  const contextValue = useMemo(
    () => ({ filters, updateFilter, resetFilters }),
    [filters, updateFilter, resetFilters]
  )

  return (
    <DashboardContext.Provider value={contextValue}>
      <div>{children}</div>
    </DashboardContext.Provider>
  )
}
```

### Why This Works

1. **`'use client'` at the top**: Declares this component and all imports as Client Components. This is required because we use `useState` and context.

2. **State in layout**: App Router layouts preserve state during navigation. When users navigate between `/conversations`, `/conversations/[id]`, etc., the filter state persists.

3. **useCallback hooks**: Creates stable function references. This is critical in React 19 because:
   - The callbacks don't get recreated on every render
   - Child components that depend on these callbacks won't re-render unnecessarily
   - Dependency array is checked strictly in React 19

4. **useMemo for context value**: Prevents unnecessary re-renders of child components:
   ```typescript
   // Without useMemo - children re-render even if filters haven't changed
   <DashboardContext.Provider value={{ filters, updateFilter, resetFilters }}>

   // With useMemo - children only re-render if filters/callbacks actually change
   const contextValue = useMemo(() => ({ filters, updateFilter, resetFilters }), [...])
   <DashboardContext.Provider value={contextValue}>
   ```

### Next.js 15 + React 19 Specific Behavior

**Layout Rendering in App Router:**

```
Initial Page Load: /conversations
  → Root layout renders
  → (dashboard) layout renders
  → conversations/layout.tsx renders (state initialized)
  → conversations/page.tsx renders

User clicks "Drafts" toggle:
  → State updates in layout
  → Layout component re-renders
  → conversations/page.tsx re-renders (with new context)
  → conversations/layout.tsx does NOT re-render again

User navigates to /conversations/123:
  → [id]/page.tsx renders
  → conversations/layout.tsx does NOT re-render (state preserved!)
  → Filters remain the same

User clicks "Published" toggle:
  → State updates in layout
  → [id]/page.tsx re-renders
  → Filter state still there when navigating back
```

**Comparison with Pages Router:**

In Pages Router (old way), navigating between pages would cause the layout to re-render, resetting your state. App Router doesn't do this - **layouts persist state on navigation**. This is a major advantage for filter state!

---

## Q2: How to properly type the context with filter callbacks?

### Answer

**Complete Type Definition Pattern:**

```typescript
// frontend/src/features/dashboard/contexts/DashboardContext.tsx
'use client'

import { createContext, useContext, ReactNode } from 'react'

// 1. Define filter shape
export interface ConversationFilters {
  archived?: boolean
  drafts?: boolean
  published?: boolean
  [key: string]: boolean | undefined // Allow dynamic filters
}

// 2. Define context shape - this is CRITICAL for type safety
export interface DashboardContextType {
  // State
  filters: ConversationFilters

  // Callbacks - use explicit function signatures
  updateFilter: (key: string, value: boolean) => void
  resetFilters: () => void
}

// 3. Create context with type - default is undefined
const DashboardContext = createContext<DashboardContextType | undefined>(undefined)

// 4. Custom hook that guarantees context exists
export function useDashboardContext(): DashboardContextType {
  const context = useContext(DashboardContext)

  if (!context) {
    throw new Error(
      'useDashboardContext must be used within a component wrapped by DashboardContext.Provider'
    )
  }

  return context
}

// 5. Export for provider
export { DashboardContext }
```

### Why Each Part Matters

**1. ConversationFilters Interface:**
```typescript
export interface ConversationFilters {
  archived?: boolean      // Optional - can be undefined
  drafts?: boolean        // Optional
  published?: boolean     // Optional
  [key: string]: boolean | undefined  // Allow extensibility
}
```

- **Optional properties (`?`)**: Not all filters need to be set
- **Index signature (`[key: string]`)**: Allows adding new filters dynamically without changing the type
- **Example**: If you later add `favorited?: boolean`, the code still works with the index signature

**2. DashboardContextType Interface:**
```typescript
export interface DashboardContextType {
  filters: ConversationFilters
  updateFilter: (key: string, value: boolean) => void  // Clear signature
  resetFilters: () => void                             // Takes no args
}
```

- **Explicit function signatures**: TypeScript knows exactly what parameters and return types are expected
- **Makes contract clear**: Any component using this context knows exactly what it gets
- **Enables autocomplete**: IDEs can provide better suggestions

**3. Context with Type Argument:**
```typescript
const DashboardContext = createContext<DashboardContextType | undefined>(undefined)
```

- **Generic type**: `<DashboardContextType | undefined>` tells TypeScript the shape
- **Undefined default**: Context is undefined until provider is used
- **Type safety**: Without this, context would be `unknown` type

**4. Custom Hook with Type Guard:**
```typescript
export function useDashboardContext(): DashboardContextType {
  const context = useContext(DashboardContext)

  if (!context) {
    throw new Error('...')  // This guards against missing provider
  }

  return context  // Now TypeScript knows this is never undefined
}
```

- **Return type**: `DashboardContextType` (not nullable)
- **Error handling**: Throws descriptive error if provider is missing
- **Usage safety**: Consumers always get a valid context

### Using the Typed Context

```typescript
// This component can safely use the context
export function FilterControls() {
  const { filters, updateFilter } = useDashboardContext()

  // TypeScript knows:
  // - filters is ConversationFilters
  // - updateFilter is (key: string, value: boolean) => void

  updateFilter('drafts', true)  // TypeScript validates this call

  return (
    <button onClick={() => updateFilter('drafts', !filters.drafts)}>
      Drafts: {filters.drafts ? 'On' : 'Off'}
    </button>
  )
}
```

### React 19 Type Safety Improvements

React 19 is stricter about types than React 18:

```typescript
// React 19 - stricter type checking
const { filters, updateFilter } = useDashboardContext()

// ❌ Would cause TypeScript error - updateFilter expects string, boolean
updateFilter(123, 'yes')

// ✅ Correct - matches function signature
updateFilter('drafts', true)
```

If you don't define types properly:

```typescript
// Bad - creates type safety issues
const context = useContext(SomeContext)  // type is 'unknown'
const result = context.filters            // ❌ 'unknown' has no 'filters'
```

**With proper typing:**

```typescript
// Good - full type safety
const context = useContext(DashboardContext)  // type is 'DashboardContextType | undefined'
const { filters } = useDashboardContext()     // type is 'DashboardContextType'
const result = filters.drafts                 // ✅ TypeScript knows this exists and is boolean
```

---

## Q3: Any React 19 considerations for the toggle button handlers?

### Answer

Yes, there are subtle but important changes in React 19:

### React 19 Event Handler Changes

**1. Type Inference is Better**

```typescript
// React 18 - need explicit types
<button onClick={(e: React.MouseEvent) => updateFilter('drafts', !filters.drafts)}>

// React 19 - type inference works better
<button onClick={() => updateFilter('drafts', !filters.drafts)}>
```

React 19 automatically infers that `onClick` expects `() => void`, so you don't need to type `e: React.MouseEvent`.

**2. Callback Dependencies Matter More**

In React 19, the dependency checking is stricter. This matters for toggle handlers:

```typescript
// Bad - creates new function on every render
const IdeationQueueHeader = () => {
  const { filters, updateFilter } = useDashboardContext()

  return (
    <button
      onClick={() => updateFilter('drafts', !filters.drafts)}
    >
      Drafts
    </button>
  )
}
// The onClick callback is recreated on every render
```

```typescript
// Better - but still memoizes the handler
const IdeationQueueHeader = () => {
  const { filters, updateFilter } = useDashboardContext()

  const handleDraftsToggle = useCallback(() => {
    updateFilter('drafts', !filters.drafts)
  }, [updateFilter, filters])

  return (
    <button onClick={handleDraftsToggle}>
      Drafts
    </button>
  )
}
// Now the handler only changes when updateFilter or filters change
```

```typescript
// Best - simple inline, let React optimize
const IdeationQueueHeader = () => {
  const { filters, updateFilter } = useDashboardContext()

  return (
    <button
      onClick={() => updateFilter('drafts', !filters.drafts)}
    >
      Drafts
    </button>
  )
}
// React 19 handles this efficiently without extra memoization
```

### Recommendation for Your Case

For simple toggle buttons, **inline handlers are fine**:

```typescript
// This is perfectly fine in React 19
<button
  onClick={() => updateFilter('drafts', !filters.drafts)}
  aria-pressed={filters.drafts}
>
  Drafts
</button>
```

**But if** the component receives the handler as a prop to a reusable component:

```typescript
// Reusable component
interface FilterToggleButtonProps {
  onChange: (value: boolean) => void  // Handler as prop
  isActive: boolean
}

export function FilterToggleButton({ onChange, isActive }: FilterToggleButtonProps) {
  return (
    <button
      onClick={() => onChange(!isActive)}
      aria-pressed={isActive}
    >
      Toggle
    </button>
  )
}

// Using it - ensure handler is memoized
const IdeationQueueHeader = () => {
  const { filters, updateFilter } = useDashboardContext()

  const handleDraftsToggle = useCallback(
    (value: boolean) => updateFilter('drafts', value),
    [updateFilter]  // Only depends on updateFilter
  )

  return (
    <FilterToggleButton
      isActive={filters.drafts}
      onChange={handleDraftsToggle}  // Stable reference
    />
  )
}
```

### React 19 Event Handler Patterns

**Pattern 1: Simple Click Handler (No Arguments)**

```typescript
// Good - simple and readable
<button onClick={() => updateFilter('drafts', !filters.drafts)}>
  Drafts
</button>
```

**Pattern 2: With Event Object (If Needed)**

```typescript
// If you need the event
<button
  onClick={(e) => {
    e.preventDefault()
    updateFilter('drafts', !filters.drafts)
  }}
>
  Drafts
</button>
```

**Pattern 3: Dynamic Filter Key**

```typescript
// Good for multiple similar buttons
const toggleFilter = (key: 'drafts' | 'published' | 'archived') => {
  updateFilter(key, !filters[key])
}

<button onClick={() => toggleFilter('drafts')}>Drafts</button>
<button onClick={() => toggleFilter('published')}>Published</button>
<button onClick={() => toggleFilter('archived')}>Archived</button>
```

### React 19 Accessibility Improvements

React 19 improved support for ARIA attributes:

```typescript
<button
  onClick={() => updateFilter('drafts', !filters.drafts)}
  aria-pressed={filters.drafts}  // React 19 handles this better
  type="button"                   // Always specify type for buttons
>
  Drafts
</button>
```

### React 19 Key Changes for Events

1. **Better type inference** - Less need for explicit type annotations
2. **Stricter closure checking** - useCallback dependencies are checked more carefully
3. **Form improvements** - Better form handling (not directly relevant here)
4. **No breaking changes** for basic event handlers - Your onclick code will work as is

### What NOT to do in React 19

```typescript
// ❌ Don't use function.bind
<button onClick={handleClick.bind(this)}>

// ❌ Don't use function() {} in handler
<button onClick={function() { updateFilter(...) }}>

// ❌ Don't forget useCallback if passing handlers as props deeply
<ComponentA><ComponentB><ComponentC handler={notMemoizedHandler} /></ComponentC></ComponentB></ComponentA>
```

### What TO do in React 19

```typescript
// ✅ Use arrow functions
<button onClick={() => updateFilter('drafts', !filters.drafts)}>

// ✅ Use useCallback if handler is passed as prop
const handler = useCallback(() => updateFilter('drafts', !filters.drafts), [updateFilter])

// ✅ Type handlers properly
onClick: (e: React.MouseEvent<HTMLButtonElement>) => void

// ✅ Use aria-pressed for toggle buttons
<button aria-pressed={isActive}>
```

---

## Q4: Best practice for URL query params with filters?

### Answer

### Approach 1: Read-Only URL (Simplest)

If you don't need bookmarkable URLs, just use state. This is the simplest approach.

```typescript
// No URL sync - just state
'use client'
const [filters, setFilters] = useState({ drafts: true, published: true })
```

### Approach 2: Read from URL on Mount (Recommended)

Initialize filters from URL, but don't keep them sync'd:

```typescript
'use client'

import { useSearchParams } from 'next/navigation'
import { useState } from 'react'

export default function ConversationsLayout({ children }: { children: ReactNode }) {
  const searchParams = useSearchParams()

  const [filters, setFilters] = useState(() => ({
    archived: searchParams.get('archived') === 'true',
    drafts: searchParams.get('drafts') !== 'false',
    published: searchParams.get('published') !== 'false',
  }))

  // ... rest of state management
}
```

**Pros:**
- Bookmarkable: Users can copy/paste URL with filters
- Simple: Minimal code changes
- No duplication: Filters in state only

**Cons:**
- URL doesn't update on filter change (users can't copy current URL)
- Browser back/forward won't restore filters

### Approach 3: Sync Filters with URL (Full Implementation)

Keep filters and URL in sync for complete bookmarkability:

```typescript
'use client'

import { useRouter, useSearchParams } from 'next/navigation'
import { useState, useCallback } from 'react'

export default function ConversationsLayout({ children }: { children: ReactNode }) {
  const router = useRouter()
  const searchParams = useSearchParams()

  const [filters, setFilters] = useState(() => ({
    archived: searchParams.get('archived') === 'true',
    drafts: searchParams.get('drafts') !== 'false',
    published: searchParams.get('published') !== 'false',
  }))

  const updateFilter = useCallback((key: string, value: boolean) => {
    // Update local state
    setFilters(prev => ({ ...prev, [key]: value }))

    // Update URL
    const params = new URLSearchParams(searchParams)
    if (value) {
      params.set(key, 'true')
    } else {
      params.delete(key)
    }

    // Use shallow=true to avoid re-rendering the page
    router.push(`?${params.toString()}`, { scroll: false })
  }, [router, searchParams])

  const resetFilters = useCallback(() => {
    setFilters({
      archived: false,
      drafts: true,
      published: true,
    })
    router.push('?', { scroll: false })
  }, [router])

  // ... provide via context
}
```

**Example URLs:**

```
/conversations
  → All defaults (drafts=true, published=true, archived=false)

/conversations?drafts=true&published=false&archived=false
  → Only drafts shown

/conversations?drafts=true&published=true&archived=true
  → All types shown

/conversations?archived=true
  → Only archived shown
```

**Pros:**
- Fully bookmarkable: Users can share exact filter state
- Browser back/forward works
- Browser history shows filter changes
- Shareable URLs

**Cons:**
- More complex code
- Additional `useRouter` call
- Slight performance overhead

### Approach 4: Server Component Search Params (Advanced)

If using Server Components, you can read params directly:

```typescript
// frontend/src/app/(dashboard)/conversations/page.tsx
// Server Component

import { SearchParams } from 'next'

export default async function ConversationsPage({
  searchParams,
}: {
  searchParams: Promise<{ [key: string]: string | string[] | undefined }>
}) {
  const params = await searchParams

  const filters = {
    archived: params.archived === 'true',
    drafts: params.drafts !== 'false',
    published: params.published !== 'false',
  }

  // Pass to client component or use directly in server component
  return <ConversationsList filters={filters} />
}
```

**Pros:**
- Works in Server Components
- Type-safe params
- No hook needed

**Cons:**
- Requires different pattern for each page
- Less flexible

### Recommendation for Your Project

**Use Approach 2** (Read from URL on Mount):

1. Simple implementation
2. Supports bookmarkable URLs
3. Doesn't require complex sync logic
4. Matches Next.js 15 best practices

```typescript
'use client'

import { useSearchParams } from 'next/navigation'
import { useState } from 'react'

export default function ConversationsLayout({ children }: { children: ReactNode }) {
  const searchParams = useSearchParams()

  const [filters, setFilters] = useState(() => ({
    archived: searchParams.get('archived') === 'true',
    drafts: searchParams.get('drafts') !== 'false',
    published: searchParams.get('published') !== 'false',
  }))

  const updateFilter = useCallback((key: string, value: boolean) => {
    setFilters(prev => ({ ...prev, [key]: value }))
  }, [])

  // ... rest of implementation
}
```

### URL Query String Best Practices

**1. Use boolean-like strings:**
```
?drafts=true&published=true&archived=false
```

**2. Only include truthy values (optional):**
```
/conversations?drafts=true&published=true
  // archived=false is implied (default)
```

**3. Use standard URL encoding:**
```
// Good
URLSearchParams.toString()

// Don't do this manually
'?drafts=true&published=true'
```

**4. Handle missing params gracefully:**
```typescript
const drafts = searchParams.get('drafts') !== 'false'  // Defaults to true
const archived = searchParams.get('archived') === 'true'  // Defaults to false
```

### Which Approach to Choose?

| Approach | Use When | Complexity |
|----------|----------|-----------|
| No URL | Internal filters, no sharing | Simple |
| Read from URL | Bookmarkable but not synced | Medium |
| Sync with URL | Full bookmarkable + history | Complex |
| Server Component | Pre-filtering data | Medium |

**For Conversations Filter Feature: Use Approach 2**
- Users can copy URL with their filter preferences
- Code is straightforward
- Aligns with Next.js 15 best practices
- Easy to extend later if needed

---

## Summary Table

| Question | Answer | Complexity |
|----------|--------|-----------|
| State management | Use `useState` in layout with Context | Medium |
| Context typing | Create `DashboardContextType` interface | Medium |
| React 19 events | Inline arrow functions work well | Simple |
| URL params | Use `useSearchParams` for bookmarks | Optional |

---

## Next Steps

1. **Implement Approach 2** for URL query params (read on mount, state-driven)
2. **Create DashboardContext** with proper TypeScript typing
3. **Update layout.tsx** with state and context provider
4. **Use FilterToggleButton** component from quick reference
5. **Test filter persistence** during navigation

All patterns use Next.js 15.4.8 + React 19.1.2 best practices.
