# Implementation Checklist: Conversations Filter Feature

## Pre-Implementation

- [ ] Read `02a-IMPLEMENTATION-SUMMARY.md`
- [ ] Read `02a-ARCHITECTURE-DIAGRAM.md`
- [ ] Review `02a-nextjs-15-quick-reference.md` - Sections 1-2
- [ ] Understand your specific questions answered in `02a-nextjs-15-qa.md`

## Phase 1: Context Setup (5 minutes)

### Create DashboardContext.tsx

**File**: `frontend/src/features/dashboard/contexts/DashboardContext.tsx`

- [ ] Create file in correct directory
- [ ] Add `'use client'` directive at top
- [ ] Define `ConversationFilters` interface
  - [ ] archvied?: boolean
  - [ ] drafts?: boolean
  - [ ] published?: boolean
  - [ ] [key: string]: boolean | undefined
- [ ] Define `DashboardContextType` interface
  - [ ] filters: ConversationFilters
  - [ ] updateFilter: (key: string, value: boolean) => void
  - [ ] resetFilters: () => void
- [ ] Create DashboardContext with type parameter
- [ ] Create useDashboardContext() hook
  - [ ] Check for undefined and throw error
  - [ ] Return typed context
- [ ] Export all three items

**Verification**: TypeScript shows no errors on file

---

## Phase 2: Layout State Management (10 minutes)

### Update conversations/layout.tsx

**File**: `frontend/src/app/(dashboard)/conversations/layout.tsx`

- [ ] Add `'use client'` directive at top
- [ ] Import required hooks
  - [ ] useState
  - [ ] useCallback
  - [ ] useMemo
  - [ ] ReactNode
- [ ] Import DashboardContext and ConversationFilters
- [ ] Define component interface with children prop
- [ ] Create useState for filters
  - [ ] Initial state: {archived: false, drafts: true, published: true}
- [ ] Create updateFilter with useCallback
  - [ ] Takes (key: string, value: boolean)
  - [ ] Updates filters state
  - [ ] Empty dependency array
- [ ] Create resetFilters with useCallback
  - [ ] Resets to initial state
  - [ ] Empty dependency array
- [ ] Create contextValue with useMemo
  - [ ] Includes filters, updateFilter, resetFilters
  - [ ] Dependencies: [filters, updateFilter, resetFilters]
- [ ] Return JSX with Provider
  - [ ] Provider wraps children
  - [ ] Provider has value={contextValue}

**Verification**:
- [ ] No TypeScript errors
- [ ] Proper component render
- [ ] Layout shows in DOM

---

## Phase 3: Reusable Components (15 minutes)

### Create FilterToggleButton.tsx

**File**: `frontend/src/features/conversation/components/FilterToggleButton.tsx`

- [ ] Create file in correct directory
- [ ] Add `'use client'` directive
- [ ] Import required items
  - [ ] PropsWithChildren from react
  - [ ] clsx
- [ ] Define FilterToggleButtonProps interface
  - [ ] label: string
  - [ ] isActive: boolean
  - [ ] onChange: (value: boolean) => void
  - [ ] testId?: string
- [ ] Create component function
- [ ] Implement button element
  - [ ] type="button"
  - [ ] aria-pressed={isActive}
  - [ ] onClick={() => onChange(!isActive)}
  - [ ] className with conditional Tailwind
  - [ ] Active state: border-blue-500, bg-blue-50, text-blue-700
  - [ ] Inactive state: border-gray-300, bg-white, text-gray-600
- [ ] Include transition classes
- [ ] Display label or children

**Verification**:
- [ ] Component renders
- [ ] Toggle state updates parent
- [ ] Styling shows active/inactive
- [ ] aria-pressed attribute present

---

## Phase 4: Header Component (10 minutes)

### Update IdeationQueueHeader.tsx

**File**: `frontend/src/features/conversation/components/IdeationQueueHeader.tsx`

- [ ] Add `'use client'` directive (if not already)
- [ ] Import useDashboardContext hook
- [ ] Import FilterToggleButton component
- [ ] Get filters and updateFilter from context
  - [ ] const { filters, updateFilter } = useDashboardContext()
- [ ] Create header element
- [ ] Add title/heading
- [ ] Add filter buttons section
  - [ ] Button 1: Drafts
    - [ ] label="Drafts"
    - [ ] isActive={filters.drafts ?? false}
    - [ ] onChange={(value) => updateFilter('drafts', value)}
    - [ ] testId="filter-drafts"
  - [ ] Button 2: Published
    - [ ] label="Published"
    - [ ] isActive={filters.published ?? false}
    - [ ] onChange={(value) => updateFilter('published', value)}
    - [ ] testId="filter-published"
  - [ ] Button 3: Archived
    - [ ] label="Archived"
    - [ ] isActive={filters.archived ?? false}
    - [ ] onChange={(value) => updateFilter('archived', value)}
    - [ ] testId="filter-archived"

**Verification**:
- [ ] Header renders
- [ ] Three buttons visible
- [ ] Buttons are clickable
- [ ] No console errors

---

## Phase 5: Content Components (10 minutes)

### Create ConversationsList.tsx

**File**: `frontend/src/features/conversation/components/ConversationsList.tsx`

- [ ] Add `'use client'` directive
- [ ] Import useDashboardContext hook
- [ ] Import useEffect
- [ ] Import getConversations function
- [ ] Get filters from context
  - [ ] const { filters } = useDashboardContext()
- [ ] Create state for conversations (optional if using TanStack Query)
- [ ] Add useEffect
  - [ ] Dependencies: [filters]
  - [ ] Call getConversations(filters)
  - [ ] Handle response
  - [ ] Handle errors
- [ ] Return JSX to render conversations

**Verification**:
- [ ] Component renders
- [ ] useEffect runs on mount
- [ ] API call includes filters

### Create conversations/page.tsx (if doesn't exist)

**File**: `frontend/src/app/(dashboard)/conversations/page.tsx`

- [ ] Create file
- [ ] No `'use client'` (Server Component)
- [ ] Import components
  - [ ] IdeationQueueHeader
  - [ ] ConversationsList
- [ ] Return layout with both components

**Verification**:
- [ ] Page renders
- [ ] Header and list visible

---

## Phase 6: API Integration (10 minutes)

### Create/Update conversations-api.ts

**File**: `frontend/src/features/conversation/api/conversations-api.ts`

- [ ] Define Conversation interface (if needed)
  - [ ] id: string
  - [ ] title: string
  - [ ] status: 'draft' | 'published' | 'archived'
  - [ ] createdAt: string
  - [ ] updatedAt: string
- [ ] Create getConversations function
  - [ ] Takes ConversationFilters parameter
  - [ ] Builds URLSearchParams from filters
  - [ ] Makes fetch call to /api/conversations
  - [ ] Includes filter params in query string
  - [ ] Returns Promise<Conversation[]>
  - [ ] Has error handling
- [ ] Export function

**Example Implementation**:
```typescript
export async function getConversations(filters: ConversationFilters) {
  const params = new URLSearchParams()
  if (filters.drafts) params.append('status', 'draft')
  if (filters.published) params.append('status', 'published')
  if (filters.archived) params.append('status', 'archived')

  const response = await fetch(`/api/conversations?${params.toString()}`)
  if (!response.ok) throw new Error('Failed to fetch')
  return response.json()
}
```

**Verification**:
- [ ] Function exports correctly
- [ ] TypeScript has no errors
- [ ] Function signature matches usage

---

## Phase 7: Advanced Optional - TanStack Query (Optional, 10 minutes)

### Create useConversations.ts Hook

**File**: `frontend/src/features/conversation/hooks/useConversations.ts`

- [ ] Add `'use client'` directive
- [ ] Import useQuery from @tanstack/react-query
- [ ] Import useDashboardContext
- [ ] Import getConversations
- [ ] Create hook function
  - [ ] Get filters from context
  - [ ] Use useQuery
    - [ ] queryKey: ['conversations', filters]
    - [ ] queryFn: () => getConversations(filters)
    - [ ] staleTime: 1000 * 60 * 5
  - [ ] Return query result
- [ ] Export hook

**Verification**:
- [ ] Hook exports correctly
- [ ] TypeScript validates useQuery usage

### Update ConversationsList to use hook (Optional)

- [ ] Replace useEffect with useConversations hook
- [ ] Get data from query result
- [ ] Show loading state
- [ ] Show error state

**Verification**:
- [ ] Loading state shows while fetching
- [ ] Data displays when ready
- [ ] Error shows on failure

---

## Phase 8: Testing (10 minutes)

### Manual Testing

- [ ] Click "Drafts" toggle
  - [ ] Button shows active state (blue)
  - [ ] ConversationsList updates
  - [ ] API call includes drafts filter
- [ ] Click "Published" toggle
  - [ ] Button shows active state
  - [ ] Conversations update
  - [ ] API includes published filter
- [ ] Click "Archived" toggle
  - [ ] Button shows active state
  - [ ] Conversations update
  - [ ] API includes archived filter
- [ ] Navigate to /conversations/[id]
  - [ ] Filter state persists
  - [ ] Buttons still show previous state
- [ ] Navigate back to /conversations
  - [ ] Same filter state maintained
  - [ ] Conversations still filtered

### Browser DevTools Testing

- [ ] Open Network tab
  - [ ] Click toggle
  - [ ] Verify new API call includes filter params
  - [ ] Example: `?drafts=true&published=false`
- [ ] Open React DevTools Profiler
  - [ ] Click toggle
  - [ ] Record profile
  - [ ] Verify only necessary components re-render
  - [ ] Should NOT re-render: root layout, nav, sidebar (if any)

### TypeScript Testing

- [ ] Run `npm run lint`
  - [ ] No TypeScript errors
  - [ ] No ESLint warnings about unused imports
- [ ] No console warnings

---

## Phase 9: Code Quality (5 minutes)

- [ ] Code formatting
  - [ ] Run `npm run format`
  - [ ] Run `npm run format:check`
- [ ] Linting
  - [ ] Run `npm run lint`
  - [ ] Fix any issues with `npm run lint:fix`
- [ ] No console.log statements left
- [ ] Comments added for complex logic
- [ ] Files follow project conventions

---

## Phase 10: Final Verification (5 minutes)

### File Structure Check

```
frontend/src/
├── features/
│   ├── dashboard/
│   │   └── contexts/
│   │       └── DashboardContext.tsx          ✓ Created
│   │
│   └── conversation/
│       ├── components/
│       │   ├── IdeationQueueHeader.tsx       ✓ Updated
│       │   ├── FilterToggleButton.tsx        ✓ Created
│       │   └── ConversationsList.tsx         ✓ Created/Updated
│       ├── hooks/
│       │   └── useConversations.ts           ✓ Created (optional)
│       └── api/
│           └── conversations-api.ts          ✓ Created/Updated
│
└── app/
    └── (dashboard)/
        └── conversations/
            ├── layout.tsx                    ✓ Updated
            └── page.tsx                      ✓ Created/Updated
```

- [ ] All files created/updated
- [ ] No typos in file paths
- [ ] All imports resolve correctly

### Functionality Check

- [ ] Toggle buttons appear in header
- [ ] Buttons are clickable
- [ ] Filter state updates on click
- [ ] Buttons show active/inactive states
- [ ] API calls include filters
- [ ] Conversations list updates
- [ ] State persists on navigation
- [ ] No console errors or warnings
- [ ] TypeScript has no errors
- [ ] Linter passes

---

## Common Issues During Testing

### Issue: "useDashboardContext must be used within DashboardContext.Provider"
**Solution**:
- [ ] Verify layout.tsx has DashboardContext.Provider wrapping children
- [ ] Check provider is in correct file (conversations/layout.tsx)
- [ ] Verify Provider value prop is set correctly

### Issue: Filters don't update
**Solution**:
- [ ] Check updateFilter is called with correct parameters
- [ ] Verify onClick handler is wired correctly
- [ ] Check context value is memoized with useMemo
- [ ] Verify dependency array includes filters

### Issue: State resets on navigation
**Solution**:
- [ ] Verify layout.tsx has `'use client'` at top
- [ ] Check state is in layout, not in page
- [ ] Verify provider wraps all child pages

### Issue: API not getting filters
**Solution**:
- [ ] Check getConversations receives filters parameter
- [ ] Verify URLSearchParams builds correctly
- [ ] Check browser Network tab for query params
- [ ] Verify backend API expects same param names

### Issue: TypeScript errors
**Solution**:
- [ ] Check ConversationFilters interface is exported
- [ ] Verify DashboardContextType interface is defined
- [ ] Check useDashboardContext return type is correct
- [ ] Verify all imports are correct paths

---

## Sign-Off Checklist

### Before Considering Complete

- [ ] All files created and updated
- [ ] No TypeScript errors
- [ ] No console errors or warnings
- [ ] Toggle buttons work correctly
- [ ] Filter state persists on navigation
- [ ] API calls include correct filters
- [ ] Conversations list updates on filter change
- [ ] Code is formatted and linted
- [ ] All tests pass
- [ ] No performance issues detected
- [ ] Documentation updated (if needed)

### Ready to Merge When

- [ ] All above checked
- [ ] Code reviewed
- [ ] Feature tested in browser
- [ ] No regressions in other features
- [ ] Performance is acceptable

---

## Documentation References

- Implementation Guide: `02a-nextjs-15-guidance.md`
- Code Snippets: `02a-nextjs-15-quick-reference.md`
- Q&A: `02a-nextjs-15-qa.md`
- Architecture: `02a-ARCHITECTURE-DIAGRAM.md`
- Index: `02a-INDEX.md`

---

## Time Estimates

| Phase | Time | Status |
|-------|------|--------|
| Understanding | 10 min | |
| Phase 1: Context | 5 min | |
| Phase 2: Layout | 10 min | |
| Phase 3: FilterToggleButton | 5 min | |
| Phase 4: IdeationQueueHeader | 10 min | |
| Phase 5: ConversationsList | 10 min | |
| Phase 6: API Integration | 10 min | |
| Phase 7: TanStack Query (opt) | 10 min | |
| Phase 8: Testing | 10 min | |
| Phase 9: Code Quality | 5 min | |
| Phase 10: Verification | 5 min | |
| **Total** | **90 min** | |

---

## Version Confirmation

- [ ] Next.js: 15.4.8 ✓
- [ ] React: 19.1.2 ✓
- [ ] TypeScript: ^5 ✓
- [ ] TanStack Query: ^5.90.10 ✓

---

**Created**: 2025-12-10
**Agent**: nextjs-15-expert
**Project**: AE-Scientist
**Feature**: Conversations Filter
**Status**: Ready to Implement

Good luck with implementation! Refer back to the guidance documents as needed.
