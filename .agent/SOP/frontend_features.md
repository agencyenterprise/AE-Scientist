# SOP: Frontend Features (Component Organization)

## Related Documentation
- [Frontend Architecture](../System/frontend_architecture.md)
- [Project Architecture](../System/project_architecture.md)

---

## Overview

This SOP covers creating new features using the feature-based folder structure. Use this procedure when you need to:
- Add a complex new feature with multiple components
- Organize related components, hooks, and utilities
- Create reusable feature modules

---

## Prerequisites

- Node.js environment set up
- Understanding of the feature's UI and data requirements
- Knowledge of React hooks and component patterns

---

## Step-by-Step Procedure

### 1. Create the Feature Folder Structure

Features are organized in `frontend/src/features/` using **kebab-case** folder names. **All components go inside the `components/` subfolder**:

```
frontend/src/features/my-feature/
├── index.ts                       # Named exports (re-exports from components/)
├── components/                    # ALL components live here
│   ├── MyFeature.tsx              # Main feature component
│   ├── MyFeatureHeader.tsx
│   ├── MyFeatureContent.tsx
│   └── MyFeatureFooter.tsx
├── hooks/                         # Feature-specific hooks (optional)
│   ├── useMyFeatureState.ts
│   └── useMyFeatureActions.ts
├── utils/                         # Feature-specific utilities (optional)
│   └── myFeatureUtils.ts
├── types/                         # Feature-specific types (optional)
│   └── types.ts
└── contexts/                      # Feature-specific contexts (optional)
    └── MyFeatureContext.tsx
```

### 2. Create Components in the components/ Folder

All components, including the main feature component, go inside `components/`:

```typescript
// frontend/src/features/my-feature/components/MyFeature.tsx
"use client"

import { useMyFeatureState } from "../hooks/useMyFeatureState"
import { useMyFeatureActions } from "../hooks/useMyFeatureActions"
import { MyFeatureHeader } from "./MyFeatureHeader"
import { MyFeatureContent } from "./MyFeatureContent"
import { MyFeatureFooter } from "./MyFeatureFooter"

interface MyFeatureProps {
  initialData?: MyFeatureData
  onSave?: (data: MyFeatureData) => void
}

export function MyFeature({ initialData, onSave }: MyFeatureProps) {
  const {
    data,
    isLoading,
    error,
    setData
  } = useMyFeatureState(initialData)

  const {
    handleSave,
    handleDelete,
    handleRefresh
  } = useMyFeatureActions(data, setData, onSave)

  if (isLoading) {
    return <div className="p-4">Loading...</div>
  }

  if (error) {
    return <div className="p-4 text-red-500">Error: {error}</div>
  }

  return (
    <div className="flex flex-col h-full">
      <MyFeatureHeader
        title={data?.title}
        onRefresh={handleRefresh}
      />
      <MyFeatureContent
        data={data}
        onChange={setData}
      />
      <MyFeatureFooter
        onSave={handleSave}
        onDelete={handleDelete}
      />
    </div>
  )
}
```

### 3. Create the Index File (Named Exports)

The `index.ts` re-exports components from the `components/` folder:

```typescript
// frontend/src/features/my-feature/index.ts
export { MyFeature } from "./components/MyFeature"
export { MyFeatureHeader } from "./components/MyFeatureHeader"
export { MyFeatureContent } from "./components/MyFeatureContent"
export { MyFeatureFooter } from "./components/MyFeatureFooter"
```

### 4. Create Custom Hooks (Optional)

#### State Management Hook

```typescript
// frontend/src/features/my-feature/hooks/useMyFeatureState.ts
import { useState, useCallback, useEffect } from "react"

interface MyFeatureData {
  id?: string
  title: string
  content: string
  status: "draft" | "published"
}

interface UseMyFeatureStateReturn {
  data: MyFeatureData | null
  isLoading: boolean
  error: string | null
  setData: (data: MyFeatureData | null) => void
  updateField: <K extends keyof MyFeatureData>(
    field: K,
    value: MyFeatureData[K]
  ) => void
}

export function useMyFeatureState(
  initialData?: MyFeatureData
): UseMyFeatureStateReturn {
  const [data, setData] = useState<MyFeatureData | null>(initialData ?? null)
  const [isLoading, setIsLoading] = useState(!initialData)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (initialData) {
      setData(initialData)
      setIsLoading(false)
    }
  }, [initialData])

  const updateField = useCallback(<K extends keyof MyFeatureData>(
    field: K,
    value: MyFeatureData[K]
  ) => {
    setData(prev => prev ? { ...prev, [field]: value } : null)
  }, [])

  return {
    data,
    isLoading,
    error,
    setData,
    updateField
  }
}
```

#### Actions Hook

```typescript
// frontend/src/features/my-feature/hooks/useMyFeatureActions.ts
import { useCallback } from "react"
import { config } from "@/lib/config"

interface MyFeatureData {
  id?: string
  title: string
  content: string
  status: "draft" | "published"
}

interface UseMyFeatureActionsReturn {
  handleSave: () => Promise<void>
  handleDelete: () => Promise<void>
  handleRefresh: () => Promise<void>
}

export function useMyFeatureActions(
  data: MyFeatureData | null,
  setData: (data: MyFeatureData | null) => void,
  onSave?: (data: MyFeatureData) => void
): UseMyFeatureActionsReturn {

  const handleSave = useCallback(async () => {
    if (!data) return

    try {
      const response = await fetch(`${config.apiUrl}/my-feature`, {
        method: data.id ? "PATCH" : "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify(data)
      })

      if (!response.ok) {
        throw new Error("Failed to save")
      }

      const saved = await response.json()
      setData(saved)
      onSave?.(saved)
    } catch (error) {
      console.error("Save error:", error)
      throw error
    }
  }, [data, setData, onSave])

  const handleDelete = useCallback(async () => {
    if (!data?.id) return

    try {
      await fetch(`${config.apiUrl}/my-feature/${data.id}`, {
        method: "DELETE",
        credentials: "include"
      })
      setData(null)
    } catch (error) {
      console.error("Delete error:", error)
      throw error
    }
  }, [data, setData])

  const handleRefresh = useCallback(async () => {
    if (!data?.id) return

    try {
      const response = await fetch(
        `${config.apiUrl}/my-feature/${data.id}`,
        { credentials: "include" }
      )
      const refreshed = await response.json()
      setData(refreshed)
    } catch (error) {
      console.error("Refresh error:", error)
    }
  }, [data, setData])

  return {
    handleSave,
    handleDelete,
    handleRefresh
  }
}
```

### 5. Create Sub-Components

```typescript
// frontend/src/features/my-feature/components/MyFeatureHeader.tsx
interface MyFeatureHeaderProps {
  title?: string
  onRefresh: () => void
}

export function MyFeatureHeader({ title, onRefresh }: MyFeatureHeaderProps) {
  return (
    <header className="flex items-center justify-between p-4 border-b">
      <h2 className="text-xl font-semibold">{title || "Untitled"}</h2>
      <button
        onClick={onRefresh}
        className="px-3 py-1 text-sm bg-gray-100 rounded hover:bg-gray-200"
      >
        Refresh
      </button>
    </header>
  )
}
```

### 6. Create Utility Functions (Optional)

```typescript
// frontend/src/features/my-feature/utils/myFeatureUtils.ts
import type { MyFeatureData } from "../hooks/useMyFeatureState"

export function validateMyFeature(data: MyFeatureData): string[] {
  const errors: string[] = []

  if (!data.title || data.title.length < 3) {
    errors.push("Title must be at least 3 characters")
  }

  if (!data.content || data.content.length < 10) {
    errors.push("Content must be at least 10 characters")
  }

  return errors
}
```

---

## Existing Features

Current features in the codebase:

| Feature | Path | Description |
|---------|------|-------------|
| `conversation` | `src/features/conversation/` | Conversation views, cards, header, title editor |
| `conversation-import` | `src/features/conversation-import/` | Import from ChatGPT, Claude, Grok URLs |
| `project-draft` | `src/features/project-draft/` | Project drafting with chat, diff viewer (30+ components) |
| `input-pipeline` | `src/features/input-pipeline/` | Hypothesis creation form with model selection |
| `model-selector` | `src/features/model-selector/` | Model selection dropdown UI |
| `research` | `src/features/research/` | Research run management, history display, status utilities |
| `search` | `src/features/search/` | Vector-based semantic search |
| `dashboard` | `src/features/dashboard/` | Dashboard-specific components |
| `layout` | `src/features/layout/` | Sidebar navigation |
| `imported-chat` | `src/features/imported-chat/` | Imported chat tab display |
| `user-profile` | `src/features/user-profile/` | User profile dropdown |

### Project-Draft Feature (Component Decomposition Example)

The `project-draft` feature demonstrates a well-modularized component structure with 30+ components:

**Main Components:**
- `ProjectDraft.tsx` - Main feature container
- `ChatMessage.tsx` - Individual chat message display
- `ChatInputArea.tsx` - Chat input with file upload
- `ChatMarkdown.tsx` - Markdown rendering for chat
- `ChatStreamingMessage.tsx` - Streaming message indicator
- `DiffViewer.tsx` - Side-by-side diff display
- `StringSection.tsx` - Generic string section with variants (used by section components)

**Section Components:**
- `AbstractSection.tsx` - Abstract content section (uses StringSection)
- `HypothesisSection.tsx` - Hypothesis display (uses StringSection)
- `RelatedWorkSection.tsx` - Related work references (uses StringSection)
- `ExpectedOutcomeSection.tsx` - Expected outcomes (uses StringSection)
- `ExperimentsSection.tsx` - Experiment descriptions
- `RiskFactorsSection.tsx` - Risk factors

**Hooks:**
- `useChatMessages.ts` - Chat message state management
- `useChatStreaming.ts` - SSE streaming for chat responses
- `useChatFileUpload.ts` - File upload handling
- `useVersionManagement.ts` - Version history management
- `useProjectDraftState.ts` - Overall feature state (facade)
- `use-project-draft-data.ts` - Data loading and polling (sub-hook)
- `use-project-draft-edit.ts` - Edit mode state (sub-hook)

### Generic Component Pattern (StringSection)

> Added from: frontend-solid-refactoring implementation (2025-12-03)

When you have 3+ nearly-identical components differing only in styling/content, create a generic component with variants:

```typescript
// features/project-draft/components/StringSection.tsx
import { cn } from "@/shared/lib/utils"

type StringSectionVariant = 'default' | 'primary-border' | 'success-box'

interface StringSectionProps {
  title: string
  content: string
  diffContent?: React.ReactElement[] | null
  onEdit?: () => void
  variant?: StringSectionVariant
  className?: string
}

const variantStyles: Record<StringSectionVariant, { container: string; content: string }> = {
  default: {
    container: '',
    content: 'text-foreground/90',
  },
  'primary-border': {
    container: 'border-l-4 border-primary pl-4',
    content: 'text-foreground',
  },
  'success-box': {
    container: 'bg-green-50 dark:bg-green-950/20 rounded-lg p-4',
    content: 'text-foreground',
  },
}

export function StringSection({
  title,
  content,
  diffContent,
  onEdit,
  variant = 'default',
  className,
}: StringSectionProps) {
  const styles = variantStyles[variant]

  return (
    <div className={cn('relative group', styles.container, className)}>
      <div className="flex items-center justify-between mb-2">
        <h3 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
          {title}
        </h3>
        {onEdit && (
          <button onClick={onEdit} className="opacity-0 group-hover:opacity-100">
            <Pencil className="h-4 w-4" />
          </button>
        )}
      </div>
      <div className={cn('prose prose-sm max-w-none', styles.content)}>
        {diffContent ?? <ReactMarkdown>{content}</ReactMarkdown>}
      </div>
    </div>
  )
}
```

**Usage in existing section components:**
```typescript
// HypothesisSection.tsx
export function HypothesisSection({ content, diffContent, onEdit }: Props) {
  return (
    <StringSection
      title="Hypothesis"
      content={content}
      diffContent={diffContent}
      onEdit={onEdit}
      variant="primary-border"
    />
  )
}
```

---

## Key Files

| File | Purpose |
|------|---------|
| `src/features/my-feature/index.ts` | Named exports (entry point) |
| `src/features/my-feature/components/` | ALL components (main + sub) |
| `src/features/my-feature/hooks/` | Feature-specific hooks |
| `src/features/my-feature/utils/` | Utility functions |
| `src/features/my-feature/types/` | TypeScript types |
| `src/features/my-feature/contexts/` | React contexts |

---

## Naming Conventions

| Item | Convention | Example |
|------|------------|---------|
| Feature folder | kebab-case | `input-pipeline`, `project-draft` |
| Component files | PascalCase | `CreateHypothesisForm.tsx` |
| Hook files | camelCase with `use` prefix | `useMyFeatureState.ts` |
| Utility files | camelCase | `myFeatureUtils.ts` |
| Type files | camelCase | `types.ts` |

---

## Hook Splitting Pattern (Facade)

> Added from: frontend-solid-refactoring implementation (2025-12-03)

When a hook grows beyond ~200 lines or manages multiple unrelated concerns, split it using the **facade pattern** to maintain backward compatibility.

### When to Use

- Hook exceeds 200 lines
- Hook manages 3+ distinct concerns (e.g., form state, streaming, conflict resolution)
- Different consumers need different subsets of the hook's functionality
- Testing individual concerns is difficult

### How to Implement

1. **Identify distinct concerns** in the large hook
2. **Create focused sub-hooks** for each concern
3. **Keep the original hook as a facade** that composes sub-hooks
4. **Preserve the original API** so existing consumers don't break

### Example

**Before** (500+ line hook with multiple concerns):
```typescript
// useConversationImport.ts - TOO LARGE
export function useConversationImport() {
  // Form state (url, error)
  const [url, setUrl] = useState('');
  const [error, setError] = useState('');

  // Streaming state
  const [isStreaming, setIsStreaming] = useState(false);
  const [sections, setSections] = useState({});

  // Conflict resolution
  const [hasConflict, setHasConflict] = useState(false);
  const [conflicts, setConflicts] = useState([]);

  // ... 400+ more lines mixing all concerns
}
```

**After** (facade with focused sub-hooks):
```typescript
// use-import-form-state.ts (~90 lines)
export function useImportFormState() {
  const [url, setUrl] = useState('');
  const [error, setError] = useState('');

  const validate = useCallback(() => {
    if (!validateUrl(url)) {
      setError(getUrlValidationError());
      return false;
    }
    return true;
  }, [url]);

  return {
    state: { url, error },
    actions: { setUrl, setError, validate, reset }
  };
}

// use-import-conflict-resolution.ts (~120 lines)
export function useImportConflictResolution() {
  const [hasConflict, setHasConflict] = useState(false);
  const [conflicts, setConflicts] = useState([]);
  // ... focused on conflict handling only

  return {
    conflict: { hasConflict, items: conflicts, selectedId },
    actions: { setConflict, selectConflict, clearConflict }
  };
}

// useConversationImport.ts - FACADE (~150 lines)
export function useConversationImport(options) {
  // Compose sub-hooks
  const formState = useImportFormState();
  const conflictState = useImportConflictResolution();
  const streaming = useStreamingImport({ onSuccess: options.onSuccess });

  // Coordinate between sub-hooks
  const startImport = useCallback(async () => {
    if (!formState.actions.validate()) return;
    await streaming.actions.startStream({ url: formState.state.url });
  }, [formState, streaming]);

  // Return SAME API as before for backward compatibility
  return {
    state: { url: formState.state.url, error: formState.state.error, ... },
    conflict: conflictState.conflict,
    actions: { setUrl: formState.actions.setUrl, startImport, ... },
  };
}
```

### Benefits

- Each sub-hook is independently testable
- Consumers can import sub-hooks directly for granular access
- Original API preserved (no breaking changes)
- Clear separation of concerns
- Smaller, more maintainable files

### File Structure After Splitting

```
features/conversation-import/hooks/
  useConversationImport.ts           # Facade (composes sub-hooks)
  use-import-form-state.ts           # Sub-hook: form state
  use-import-conflict-resolution.ts  # Sub-hook: conflict handling
```

---

## Hook Return Pattern

Always return an object with named properties:

```typescript
interface UseMyHookReturn {
  // State
  data: DataType
  isLoading: boolean
  error: string | null

  // Actions
  handleSave: () => Promise<void>
  handleDelete: () => Promise<void>

  // Utilities
  validate: () => boolean
  format: (value: string) => string
}
```

---

## Common Pitfalls

- **Never use default exports**: Use named exports in `index.ts`
- **All components in components/ folder**: Don't put components at the feature root
- **Always use `useCallback`**: Wrap all functions that are passed as props
- **Separate concerns**: State logic in hooks, UI in components
- **Co-locate hooks**: Keep feature-specific hooks inside the feature folder
- **Type all props**: Define interfaces for all component props
- **Use kebab-case for folders**: Feature folders use kebab-case (e.g., `my-feature`)

---

## Filter UI Pattern

> Added from: log-level-filter implementation (2025-12-04)

When adding filter buttons to a component (e.g., log level filters, status filters), follow this pattern:

### Configuration Object

Use a Record to map filter values to their display properties. This ensures explicit Tailwind classes (required for Tailwind v4):

```typescript
type LogLevelFilter = "all" | "info" | "warn" | "error";

const LOG_FILTER_CONFIG: Record<LogLevelFilter, { label: string; activeClass: string }> = {
  all: { label: "all", activeClass: "bg-slate-500/15 text-slate-300" },
  info: { label: "info", activeClass: "bg-sky-500/15 text-sky-400" },
  warn: { label: "warn", activeClass: "bg-amber-500/15 text-amber-400" },
  error: { label: "error", activeClass: "bg-red-500/15 text-red-400" },
};

const LOG_FILTER_OPTIONS: LogLevelFilter[] = ["all", "info", "warn", "error"];
```

### Header with Inline Filters

Place filter buttons in the card header using flexbox `justify-between`:

```typescript
<div className="mb-4 flex items-center justify-between">
  {/* Left side: Icon, Title, Count */}
  <div className="flex items-center gap-2">
    <Terminal className="h-5 w-5 text-slate-400" />
    <h2 className="text-lg font-semibold text-white">Logs</h2>
    <span className="text-sm text-slate-400">
      ({filteredLogs.length}{activeFilter !== "all" ? `/${logs.length}` : ""})
    </span>
  </div>

  {/* Right side: Filter Buttons */}
  <div className="flex items-center gap-1" role="group" aria-label="Log level filter">
    {LOG_FILTER_OPTIONS.map(option => (
      <button
        key={option}
        type="button"
        onClick={() => setActiveFilter(option)}
        aria-pressed={activeFilter === option}
        className={cn(
          "rounded-md px-3 py-1 text-xs font-medium transition-colors",
          activeFilter === option
            ? LOG_FILTER_CONFIG[option].activeClass
            : "text-slate-500 hover:text-slate-300 hover:bg-slate-800"
        )}
      >
        {LOG_FILTER_CONFIG[option].label}
      </button>
    ))}
  </div>
</div>
```

### State and Filtering

Use `useState` for filter state and `useMemo` for derived filtered data:

```typescript
const [activeFilter, setActiveFilter] = useState<LogLevelFilter>("all");

const filteredLogs = useMemo(() => {
  if (activeFilter === "all") return logs;
  return logs.filter(log => {
    const level = log.level.toLowerCase();
    if (activeFilter === "warn") {
      return level === "warn" || level === "warning";
    }
    return level === activeFilter;
  });
}, [logs, activeFilter]);
```

### Empty State with Filter Context

Show different messages based on whether filtering caused the empty state:

```typescript
{filteredLogs.length === 0 ? (
  <div className="flex h-full items-center justify-center">
    <span className="text-slate-400">
      {activeFilter === "all" ? "No logs yet" : `No ${activeFilter}-level logs`}
    </span>
  </div>
) : (
  // Render filtered items
)}
```

### Accessibility Requirements

- Use `role="group"` on the button container
- Add `aria-label` describing the filter group (e.g., "Log level filter")
- Add `aria-pressed` to each button indicating current selection state

### Reference Implementation

See `frontend/src/features/research/components/run-detail/research-logs-list.tsx` for a complete example.

---

## Verification

1. Import the component in a page:
   ```typescript
   import { MyFeature } from "@/features/my-feature"
   ```

2. Verify all exports work:
   ```typescript
   import {
     MyFeature,
     MyFeatureHeader,
     MyFeatureContent
   } from "@/features/my-feature"
   ```

3. Test the component renders correctly

4. Verify hooks work independently (if applicable):
   ```typescript
   import { useMyFeatureState } from "@/features/my-feature/hooks/useMyFeatureState"
   const { data, setData } = useMyFeatureState()
   ```

5. Check TypeScript types are correct (no type errors)
