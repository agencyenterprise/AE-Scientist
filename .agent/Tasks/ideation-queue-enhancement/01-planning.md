# Planning Phase

## Agent
feature-planner

## Timestamp
2025-12-05 (Initial Planning)

## Input Received

- Context: `.agent/Tasks/ideation-queue-enhancement/00-context.md`
- Project docs consulted:
  - `.agent/README.md` - Documentation index
  - `.agent/System/frontend_architecture.md` - Feature-based architecture, naming conventions
  - `.agent/System/project_architecture.md` - Overall system structure
  - `.agent/SOP/frontend_pages.md` - Page creation guidelines
  - `.agent/SOP/frontend_features.md` - Feature organization, filter UI patterns
  - `.agent/SOP/frontend_api_hooks.md` - API hook patterns

## Reasoning

### Why This Approach

The "Ideation Queue" enhancement is fundamentally a UI/UX improvement to an existing page. Rather than creating a completely new feature, we should:

1. **Enhance the existing conversation feature** - This maintains code organization and allows gradual migration
2. **Reuse patterns from research feature** - Status badges, filter UI, card layouts are already implemented
3. **Keep backward compatibility** - Don't break existing functionality during transition
4. **Plan for future API enhancement** - Design for full status support even if MVP uses derived status

### Pattern Selection

- **Chose pattern**: Enhanced feature components with utility extraction
- **Because**:
  - Follows existing project conventions (feature-based architecture)
  - Minimizes new code by reusing research utilities
  - Allows incremental migration without breaking existing functionality
- **Reference**: `features/research/components/research-board-card.tsx` and `features/research/utils/research-utils.tsx`

### Dependencies Identified

| Dependency | Source | Why Needed |
|------------|--------|------------|
| `getStatusBadge()` | `features/research/utils/research-utils.tsx` | Adapt for ideation status badges |
| `formatRelativeTime()` | `shared/lib/date-utils.ts` | Display relative dates |
| Filter UI pattern | `features/research/components/run-detail/research-logs-list.tsx` | Filter button configuration |
| `cn()` utility | `shared/lib/utils` | Conditional class merging |
| `Conversation` type | `shared/lib/api-adapters.ts` | Type definitions |
| date-fns | npm dependency | Already installed, used for date formatting |

### Risks & Considerations

| Risk | Mitigation |
|------|------------|
| Status derivation is limited without backend data | Design components to accept status as prop; MVP uses derived status, future iteration adds backend field |
| Large refactor could break existing functionality | Keep deprecated components, create new ones alongside, migrate page last |
| Tailwind v4 dynamic class issue | Follow explicit class pattern from research-utils.tsx |
| Filter state complexity | Use existing filter hook pattern, extend rather than replace |

### Alternative Approaches Considered

1. **Full route rename (`/ideation-queue`)**: Rejected for MVP - adds complexity and potential broken links. Can add later as an alias.

2. **Create new separate feature (`features/ideation-queue/`)**: Rejected - Would duplicate conversation data handling. Better to enhance existing feature.

3. **Backend-first approach (add status to API)**: Deferred - Good idea for iteration 2, but MVP can work with derived status from existing fields.

## Key Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Route path | Keep `/conversations` | Avoid breaking existing links; rename can be phase 2 |
| Feature location | Enhance `features/conversation/` | Reuse existing data flow and context |
| Status source | Derive from existing fields (MVP) | No backend changes needed for initial release |
| Component strategy | Create new components, deprecate old | Clean migration path without breaking changes |
| Badge styling | Adapt from research-utils | Consistent visual language across app |
| Filter pattern | Use LOG_FILTER_CONFIG style | Proven pattern from recent implementation |

## Output Summary

- PRD created: `.agent/Tasks/ideation-queue-enhancement/PRD.md`
- Files to create: 8 frontend files (5 components, 1 hook, 1 utility, 1 type file)
- Files to modify: 2 files (page.tsx, index.ts)
- Estimated complexity: **Moderate** - Mostly UI work reusing existing patterns

## Implementation Phases Summary

| Phase | Description | Files | Effort |
|-------|-------------|-------|--------|
| 1 | Utilities and Types | 2 new | Small |
| 2 | Core Components | 4 new | Medium |
| 3 | Filtering and Sorting | 2 new/modify | Medium |
| 4 | Page Integration | 1 modify | Small |
| 5 | Polish and Testing | - | Small |

## For Next Phase (Architecture)

Key considerations for the architect:

1. **Status Type Definition**: Define `IdeaStatus` enum matching badge display needs, keeping backward compatibility with "conversation" terminology in types

2. **Component Props Interface**: Design `IdeationQueueRow` props to accept either derived or API-provided status, enabling future backend enhancement

3. **Filter State Management**: Decide between extending `useConversationsFilter` vs creating new `useIdeationQueueFilters` hook - recommend extending for code reuse

4. **Sort Implementation**: Consider whether to sort client-side (simpler) or add backend support (better for large datasets)

5. **Mobile Breakpoints**: Define clear breakpoints for table-to-card transition (suggest md: 768px based on existing patterns)

6. **Empty State Variants**: Design empty states for:
   - No conversations at all
   - No conversations matching filter
   - No conversations matching search

## Code Snippets for Reference

### Status Type (suggested)
```typescript
// features/conversation/types/ideation-queue.types.ts
export type IdeaStatus =
  | "no_idea"        // No ideaTitle/ideaAbstract
  | "pending_launch" // Has idea, no research
  | "in_research"    // Active research run
  | "completed"      // Research completed
  | "failed";        // Research failed

export interface IdeaStatusConfig {
  label: string;
  className: string;
  icon: React.ComponentType<{ className?: string }>;
}
```

### Status Badge Pattern (from research-utils)
```typescript
// Features explicit Tailwind classes for v4 compatibility
const IDEA_STATUS_CONFIG: Record<IdeaStatus, IdeaStatusConfig> = {
  no_idea: {
    label: "No idea",
    className: "bg-slate-500/15 text-slate-400",
    icon: FileQuestion,
  },
  pending_launch: {
    label: "Pending launch",
    className: "bg-amber-500/15 text-amber-400",
    icon: Clock,
  },
  // ...
};
```

### Filter Configuration Pattern (from research-logs-list)
```typescript
const STATUS_FILTER_OPTIONS: IdeaStatus[] = [
  "all",
  "no_idea",
  "pending_launch",
  "in_research",
  "completed",
  "failed",
];
```

## Approval Status

- [ ] Pending approval
- [ ] Approved - proceed to Architecture
- [ ] Modified - see feedback below

### Feedback (if modified)
{User feedback will be added here}
