## 🔍 Feature Area: React 19 ESLint Errors - useState in useEffect Anti-patterns

## Summary

15 ESLint errors from new React 19 rules (`react-hooks/set-state-in-effect` and `react-hooks/immutability`). Errors span 10 files, primarily modal components with SSR guards and state synchronization patterns that violate cascading render prevention rules.

## Code Paths Found

### SSR Guard Pattern (6 locations)

Pattern: `useState(false)` + `useEffect(() => setIsClient(true), [])` for client-only rendering.

| File                                                                              | Lines | Purpose                         | Action |
| --------------------------------------------------------------------------------- | ----- | ------------------------------- | ------ |
| `frontend/src/features/conversation/components/CostDetailModal.tsx`               | 17-21 | SSR guard for portal rendering  | modify |
| `frontend/src/features/conversation/components/DeleteConfirmModal.tsx`            | 22-26 | SSR guard for portal rendering  | modify |
| `frontend/src/features/project-draft/components/ArraySectionEditModal.tsx`        | 35-41 | SSR guard for portal rendering  | modify |
| `frontend/src/features/project-draft/components/SectionEditModal.tsx`             | 26-30 | SSR guard for portal rendering  | modify |
| `frontend/src/features/research/components/run-detail/review/ReviewModal.tsx`     | 51-60 | SSR guard + focus management    | modify |
| `frontend/src/features/input-pipeline/components/HypothesisConfirmationModal.tsx` | N/A   | No SSR guard (not using portal) | skip   |

### Modal State Reset Pattern (3 locations)

Pattern: `useEffect(() => { setState(props), [] }, [isOpen, props])` - synchronizes modal state with props.

| File                                                                              | Lines | Purpose                                   | Action |
| --------------------------------------------------------------------------------- | ----- | ----------------------------------------- | ------ |
| `frontend/src/features/project-draft/components/SectionEditModal.tsx`             | 33-38 | Reset `editContent` when modal opens      | modify |
| `frontend/src/features/project-draft/components/ArraySectionEditModal.tsx`        | 44-58 | Reset `editItems` and `singleItemContent` | modify |
| `frontend/src/features/input-pipeline/components/HypothesisConfirmationModal.tsx` | 24-27 | Sync `title` and `description` with props | modify |

### Conditional State Clear Pattern (4 locations)

Pattern: `useEffect(() => { if (!condition) setState(null) }, [condition])` - clears state based on condition.

| File                                                                     | Lines  | Purpose                                             | Action |
| ------------------------------------------------------------------------ | ------ | --------------------------------------------------- | ------ |
| `frontend/src/features/conversation/components/ConversationHeader.tsx`   | 53-57  | Clear `pendingView` when `viewMode` matches         | modify |
| `frontend/src/features/project-draft/hooks/useVersionManagement.ts`      | 92-100 | Clear version selection on mode/conversation change | modify |
| `frontend/src/features/research/components/run-detail/tree-viz-card.tsx` | 23-31  | Reset `selectedStageId` when viz data changes       | modify |

### Auth Context Initialization (2 errors)

Pattern: Two separate effects that both set state during initialization.

| File                                           | Lines   | Purpose                          | Action |
| ---------------------------------------------- | ------- | -------------------------------- | ------ |
| `frontend/src/shared/contexts/AuthContext.tsx` | 95-123  | Check OAuth errors in URL params | modify |
| `frontend/src/shared/contexts/AuthContext.tsx` | 125-128 | Check auth status on mount       | modify |

### Redundant Auto-scroll (1 error)

Pattern: Duplicate scroll logic already handled in upstream hook.

| File                                                                       | Lines   | Purpose                       | Action |
| -------------------------------------------------------------------------- | ------- | ----------------------------- | ------ |
| `frontend/src/features/conversation-import/hooks/useConversationImport.ts` | 121-126 | Auto-scroll streaming content | remove |

**Upstream implementation**: `/Users/jarbasmoraes/code/ae/ae-scientist/AE-Scientist/frontend/src/shared/hooks/use-streaming-import.ts:270` already handles scrolling in SSE event handler.

## Key Patterns

### React 19 SSR Guard Pattern

- **Old**: `useState(false)` + `useEffect(() => setIsClient(true), [])`
- **New**: `useSyncExternalStore(subscribe, getSnapshot, getServerSnapshot)`
- **Rationale**: Avoids cascading render from effect setting state

### Modal Reset Pattern

- **Old**: `useEffect(() => setState(props), [isOpen, props])`
- **New**: Parent component passes `key` prop to force remount
- **Rationale**: Component remount naturally resets state without effect

### Conditional State Clear Pattern

- **Option A**: Wrapper function combining state updates (for related state)
- **Option B**: Derived state with `useMemo` (for computed state)
- **Option C**: Parent uses `key` prop (for component-level reset)

## Integration Points

### SSR Guard Hook

- **Create**: `frontend/src/shared/hooks/use-is-client.ts`
- **Exports**: `useIsClient(): boolean`
- **Import locations**: 6 modal components

### Parent Components (Key Prop Required)

- Components rendering `SectionEditModal` must pass `key={isOpen ? sectionId : 'closed'}`
- Components rendering `ArraySectionEditModal` must pass appropriate `key` prop
- Components rendering `HypothesisConfirmationModal` must pass `key` prop

## Constraints Discovered

1. **Portal Rendering**: All SSR guard components use `createPortal(content, document.body)` - requires client-side check
2. **Modal Lifecycle**: Modals using `key` prop remount completely - ensure no state loss from parent
3. **Auth Flow**: AuthContext effects must be combined to avoid race conditions between error check and status check
4. **Scroll Performance**: Auto-scroll already handled in `use-streaming-import.ts:270` - redundant implementation in `useConversationImport.ts:121-126`

## Files to Modify (11 total)

1. `frontend/src/shared/hooks/use-is-client.ts` — **CREATE**
2. `frontend/src/features/conversation/components/CostDetailModal.tsx`
3. `frontend/src/features/conversation/components/DeleteConfirmModal.tsx`
4. `frontend/src/features/project-draft/components/ArraySectionEditModal.tsx`
5. `frontend/src/features/project-draft/components/SectionEditModal.tsx`
6. `frontend/src/features/research/components/run-detail/review/ReviewModal.tsx`
7. `frontend/src/features/input-pipeline/components/HypothesisConfirmationModal.tsx`
8. `frontend/src/features/conversation/components/ConversationHeader.tsx`
9. `frontend/src/features/project-draft/hooks/useVersionManagement.ts`
10. `frontend/src/features/research/components/run-detail/tree-viz-card.tsx`
11. `frontend/src/shared/contexts/AuthContext.tsx`
12. `frontend/src/features/conversation-import/hooks/useConversationImport.ts`

## Verification Command

```bash
npm run lint -- --max-warnings 0
```

Should show 0 errors after fixes applied.
