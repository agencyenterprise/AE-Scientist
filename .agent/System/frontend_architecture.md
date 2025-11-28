# Frontend Architecture

## Related Documentation
- [README.md](../README.md) - Documentation index
- [Project Architecture](project_architecture.md) - Overall system architecture

---

## 1. Overview

The frontend is a Next.js application providing a web interface for conversation import, AI-powered project draft generation, and real-time chat.

### Tech Stack

| Technology | Version | Purpose |
|------------|---------|---------|
| Next.js | 15.4.7 | React framework with App Router |
| React | 19.1.0 | UI library |
| TypeScript | 5.x | Type-safe JavaScript |
| Tailwind CSS | 4.x | Utility-first CSS (PostCSS plugin) |
| shadcn/ui | - | Component library (new-york style) |
| React Context | - | Feature-level state management |
| React Query | 5.90.10 | Server state management |
| react-hook-form | - | Form state management |
| Zod | 4.1.13 | Schema validation |
| Lucide React | 0.554.0 | Icon library |

### Key Capabilities
- Import conversations from ChatGPT, Claude, and Grok share URLs
- AI-powered project draft generation with version history
- Real-time streaming chat with multiple LLM providers
- Vector-based semantic search across conversations
- File attachments with model capability filtering

---

## 2. Feature-Based Architecture

### Folder Structure

The project follows a **feature-based architecture**. The `app/` directory contains routes only, while business logic is organized into features:

```
frontend/
├── src/
│   ├── app/                       # Next.js App Router (routes only)
│   │   ├── layout.tsx            # Root layout with AuthProvider & QueryProvider
│   │   ├── globals.css
│   │   ├── login/
│   │   │   └── page.tsx
│   │   └── (dashboard)/
│   │       ├── layout.tsx
│   │       ├── page.tsx
│   │       ├── conversations/
│   │       │   ├── page.tsx
│   │       │   └── [id]/
│   │       │       └── page.tsx
│   │
│   ├── features/                  # Feature-based organization
│   │   ├── conversation/          # Conversation management
│   │   ├── conversation-import/   # Import from ChatGPT, Claude, Grok
│   │   ├── project-draft/         # Project draft generation (30+ components)
│   │   ├── input-pipeline/        # Hypothesis creation form
│   │   ├── model-selector/        # Model selection UI
│   │   ├── search/                # Search functionality
│   │   ├── dashboard/             # Dashboard components
│   │   ├── layout/                # Layout components (Sidebar)
│   │   ├── imported-chat/         # Imported chat display
│   │   └── user-profile/          # User profile dropdown
│   │
│   ├── shared/                    # Shared across features
│   │   ├── components/
│   │   │   ├── ui/               # shadcn/ui components (auto-generated)
│   │   │   ├── Header.tsx
│   │   │   ├── FileUpload.tsx
│   │   │   ├── FileAttachment.tsx
│   │   │   ├── Markdown.tsx
│   │   │   └── ProtectedRoute.tsx
│   │   ├── contexts/
│   │   │   └── AuthContext.tsx
│   │   ├── providers/
│   │   │   └── QueryProvider.tsx
│   │   ├── hooks/
│   │   │   ├── useAuth.ts
│   │   │   └── useSearch.ts
│   │   └── lib/
│   │       ├── api-adapters.ts   # Anti-corruption layer for API responses
│   │       ├── auth-api.ts
│   │       ├── config.ts
│   │       ├── fileUtils.ts
│   │       ├── searchUtils.ts
│   │       └── utils.ts
│   │
│   └── types/
│       ├── api.gen.ts            # Auto-generated OpenAPI types
│       ├── index.ts
│       ├── auth.ts
│       └── search.ts
│
├── public/
├── package.json
└── next.config.ts
```

### Features Overview

| Feature | Path | Description |
|---------|------|-------------|
| `conversation` | `src/features/conversation/` | Conversation views, cards, header, title editor |
| `conversation-import` | `src/features/conversation-import/` | Import from ChatGPT, Claude, Grok URLs |
| `project-draft` | `src/features/project-draft/` | Project drafting with chat, diff viewer, sections (30+ components) |
| `input-pipeline` | `src/features/input-pipeline/` | Hypothesis creation form with model selection |
| `model-selector` | `src/features/model-selector/` | Model selection dropdown UI |
| `search` | `src/features/search/` | Vector-based semantic search |
| `dashboard` | `src/features/dashboard/` | Dashboard-specific components |
| `layout` | `src/features/layout/` | Sidebar navigation |
| `imported-chat` | `src/features/imported-chat/` | Imported chat tab display |
| `user-profile` | `src/features/user-profile/` | User profile dropdown |

### Feature Structure Template

Each feature should follow this consistent structure:

```
features/[feature]/
├── components/             # Feature-specific components
│   ├── ui/                # Feature-specific UI components
│   └── forms/             # Feature-specific forms
├── hooks/                  # Custom hooks for data/state operations
├── contexts/               # React Context (if needed for shared state)
├── types/                  # Feature-specific types (or co-locate with entities)
├── utils/                  # Feature-specific utilities
├── schemas/                # Zod validation schemas
└── index.ts                # Barrel exports
```

**Important**: Prefer entity files over separate `types/` folders. Types should be co-located with their domain entities.

---

## 3. Naming Conventions

### Files & Folders
- **Format**: `kebab-case`
- **Examples**:
  - `project-draft/`
  - `use-conversations.ts`
  - `conversation-card.tsx`
  - `api-adapters.ts`

### Hooks
- **Format**: `use-[hook-name].ts`
- **Examples**:
  - `use-auth.ts`
  - `use-search.ts`
  - `use-project-draft.ts`

### Types
- **Format**: `[feature-name].types.ts`
- **Examples**:
  - `conversation.types.ts`
  - `project-draft.types.ts`

### Import Examples

```typescript
// shadcn/ui components
import { Button } from "@/shared/components/ui/button"
import { Input } from "@/shared/components/ui/input"

// Feature imports
import { useConversationActions } from "@/features/conversation/hooks/useConversationActions"
import { ConversationCard } from "@/features/conversation/components/ConversationCard"

// Shared imports
import { cn } from "@/shared/lib/utils"
import { useAuth } from "@/shared/hooks/useAuth"
import { AuthContext } from "@/shared/contexts/AuthContext"
```

---

## 4. UI & Styling

### Component Library

**shadcn/ui** configured with:
- **Style**: "new-york"
- **Base color**: "neutral"
- **Icon library**: `lucide-react`
- **CSS variables**: enabled

### Styling Approach

- **Framework**: Tailwind CSS v4 (PostCSS plugin)
- **Global styles**: `app/globals.css`
- **Utility function**: Use `cn()` from `@/lib/utils` for conditional classes

### Component Example

```typescript
import { cn } from "@/lib/utils"

interface MyComponentProps {
  className?: string
  children: React.ReactNode
}

export function MyComponent({ className, children }: MyComponentProps) {
  return (
    <div className={cn("rounded-lg border p-4", className)}>
      {children}
    </div>
  )
}
```

---

## 5. State Management

### Local Component State
- Use React's `useState` and `useReducer`
- For simple, component-scoped state

### Feature-Level State (React Context)
- Use **React Context** in `features/[feature]/contexts/` or `shared/contexts/`
- Create a Provider component and a custom hook for consuming the context

```typescript
// features/conversation/context/ConversationContext.tsx
"use client"

import { createContext, useContext, useState, ReactNode } from "react"

interface ConversationContextValue {
  selectedConversation: Conversation | null
  setSelectedConversation: (conv: Conversation | null) => void
  isEditing: boolean
  setIsEditing: (editing: boolean) => void
}

const ConversationContext = createContext<ConversationContextValue | null>(null)

export function ConversationProvider({ children }: { children: ReactNode }) {
  const [selectedConversation, setSelectedConversation] = useState<Conversation | null>(null)
  const [isEditing, setIsEditing] = useState(false)

  return (
    <ConversationContext.Provider value={{
      selectedConversation,
      setSelectedConversation,
      isEditing,
      setIsEditing,
    }}>
      {children}
    </ConversationContext.Provider>
  )
}

export function useConversation() {
  const context = useContext(ConversationContext)
  if (!context) {
    throw new Error("useConversation must be used within ConversationProvider")
  }
  return context
}
```

### Shared Context Example (AuthContext)

```typescript
// shared/contexts/AuthContext.tsx
"use client"

import { createContext, useContext, useState, useEffect, ReactNode } from "react"

interface AuthContextValue {
  user: User | null
  isAuthenticated: boolean
  isLoading: boolean
  login: () => Promise<void>
  logout: () => Promise<void>
}

const AuthContext = createContext<AuthContextValue | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [isLoading, setIsLoading] = useState(true)

  useEffect(() => {
    checkAuthStatus()
  }, [])

  // ... implementation
}

export function useAuth() {
  const context = useContext(AuthContext)
  if (!context) {
    throw new Error("useAuth must be used within AuthProvider")
  }
  return context
}
```

### Server State (React Query)
- Use **React Query** via `QueryProvider` in `shared/providers/`
- Configuration with sensible defaults

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

---

## 6. Forms & Validation

### Form Management
- **Library**: `react-hook-form` for form state management
- **Validation**: Zod schemas with `@hookform/resolvers/zod`
- **UI Components**: shadcn/ui `Form` components
- **Location**: Place forms in `features/[feature]/components/forms/`

### Zod Schema Conventions
- Use `z.enum()` instead of deprecated `z.nativeEnum()`
- Define schemas in entity files or co-located with forms
- Export schemas for reuse in API routes and components

### Form Pattern (shadcn/ui)

```typescript
// features/projects/components/forms/create-project-form.tsx
"use client"

import { zodResolver } from "@hookform/resolvers/zod"
import { useForm } from "react-hook-form"
import { z } from "zod"
import { Button } from "@/components/ui/button"
import {
  Form,
  FormControl,
  FormDescription,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@/components/ui/form"
import { Input } from "@/components/ui/input"

const createProjectSchema = z.object({
  name: z.string().min(1, { message: "Name is required" }),
  description: z.string().optional(),
  status: z.enum(["active", "inactive"]),
})

type CreateProjectForm = z.infer<typeof createProjectSchema>

export function CreateProjectForm() {
  const form = useForm<CreateProjectForm>({
    resolver: zodResolver(createProjectSchema),
    defaultValues: {
      name: "",
      description: "",
      status: "active",
    },
  })

  function onSubmit(data: CreateProjectForm) {
    console.log(data)
  }

  return (
    <Form {...form}>
      <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-6">
        <FormField
          control={form.control}
          name="name"
          render={({ field }) => (
            <FormItem>
              <FormLabel>Project Name</FormLabel>
              <FormControl>
                <Input placeholder="My Project" {...field} />
              </FormControl>
              <FormDescription>
                The public display name for your project.
              </FormDescription>
              <FormMessage />
            </FormItem>
          )}
        />

        <FormField
          control={form.control}
          name="description"
          render={({ field }) => (
            <FormItem>
              <FormLabel>Description</FormLabel>
              <FormControl>
                <Input placeholder="Optional description" {...field} />
              </FormControl>
              <FormMessage />
            </FormItem>
          )}
        />

        <Button type="submit" disabled={form.formState.isSubmitting}>
          Create Project
        </Button>
      </form>
    </Form>
  )
}
```

### Form Guidelines
1. Always add `"use client"` directive at the top of form files
2. Use shadcn/ui `Form` components (`FormField`, `FormItem`, `FormLabel`, `FormControl`, `FormMessage`)
3. Use `render` prop pattern with `FormField` for each input
4. Keep form schemas co-located with the form component
5. Use `z.infer<typeof schema>` for type inference
6. Handle loading states with `form.formState.isSubmitting`
7. Use consistent field naming with database schema
8. `FormMessage` automatically displays validation errors
9. Use `FormDescription` for helpful field hints

---

## 7. Development Guidelines

### When Creating New Features

1. Create feature folder in `src/features/`
2. Follow the feature structure template
3. Use kebab-case for folder names
4. Define types in entity files, not separate `types/` folders
5. Use React Context for shared feature state
6. Use custom hooks for data fetching and state operations
7. Co-locate related components, hooks, and utilities

### Component Development

1. Start with shadcn/ui components when possible
2. Create feature-specific components in `src/features/[feature]/components/`
3. Create shared components in `src/shared/components/`
4. Use the `cn()` utility from `@/shared/lib/utils` for conditional classes
5. Co-locate styles with components using Tailwind

### Adding a New Page

1. Create file in `src/app/` following App Router conventions
2. Use `"use client"` directive for client components
3. Import feature components, don't put logic in page files
4. Keep pages thin - they should compose feature components

---

## 8. Type Generation (OpenAPI)

The frontend uses auto-generated TypeScript types from the backend OpenAPI spec.

### Type Generation Workflow

```bash
# Generate types from backend OpenAPI spec
npm run gen:api-types

# Or during build (automatic via prebuild hook)
openapi-typescript ../backend/openapi.json --output src/types/api.gen.ts
```

### Anti-Corruption Layer

The `api-adapters.ts` file converts backend API responses (snake_case) to frontend types (camelCase):

```typescript
// shared/lib/api-adapters.ts
import type { components } from "@/types/api.gen"

// Re-export types with frontend-friendly names
export type Conversation = components["schemas"]["Conversation"]
export type ProjectDraft = components["schemas"]["ProjectDraft"]

// Type guard for error responses
export function isErrorResponse(response: unknown): response is ErrorResponse {
  return typeof response === "object" && response !== null && "error" in response
}

// Adapter functions for API responses
export function adaptConversation(data: ApiConversation): Conversation {
  return {
    id: data.id,
    title: data.title,
    createdAt: data.created_at,
    // ... transform snake_case to camelCase
  }
}
```

---

## 9. Migration Guide

### When to Migrate

Identify code that needs migration when you see:

| Pattern | Issue | Target |
|---------|-------|--------|
| `components/FeatureName/` | Components grouped by feature in wrong location | `src/features/[feature]/components/` |
| `hooks/useSomething.ts` | Global hooks folder | `src/features/[feature]/hooks/` or `src/shared/hooks/` |
| `types/feature.ts` | Separate types folder | Co-locate with entity or `[feature].types.ts` |
| Custom form handling | Not using shadcn/ui Form | Migrate to react-hook-form + shadcn/ui |

### Migration Steps

#### 1. Moving Components to Features

```bash
# Before
components/
├── ProjectDraft/
│   ├── ProjectDraft.tsx
│   ├── hooks/useProjectDraftState.ts
│   └── components/ProjectDraftHeader.tsx

# After
src/features/project-draft/
├── components/
│   ├── ProjectDraft.tsx
│   ├── ProjectDraftHeader.tsx
│   └── forms/
├── hooks/
│   └── useProjectDraftState.ts
└── types/
    └── types.ts
```

Steps:
1. Create feature folder: `src/features/project-draft/`
2. Move components to `components/` subfolder
3. Move hooks to `hooks/` subfolder
4. Update all imports throughout the codebase
5. Delete old component folder

#### 2. Migrating Forms to shadcn/ui

```typescript
// Before: Custom form handling
function MyForm() {
  const [name, setName] = useState("")
  const [error, setError] = useState("")

  const handleSubmit = (e) => {
    e.preventDefault()
    if (!name) setError("Required")
    // ...
  }

  return (
    <form onSubmit={handleSubmit}>
      <input value={name} onChange={(e) => setName(e.target.value)} />
      {error && <span>{error}</span>}
    </form>
  )
}

// After: shadcn/ui Form with Zod
const schema = z.object({ name: z.string().min(1, "Required") })

function MyForm() {
  const form = useForm({ resolver: zodResolver(schema) })

  return (
    <Form {...form}>
      <form onSubmit={form.handleSubmit(onSubmit)}>
        <FormField name="name" render={...} />
      </form>
    </Form>
  )
}
```

### Migration Priority

1. **High Priority** (do immediately):
   - New features should always follow the new architecture
   - Fix naming conventions when touching a file

2. **Medium Priority** (when working in the area):
   - Migrate components to features when modifying them

3. **Low Priority** (dedicated refactoring):
   - Migrate all forms to shadcn/ui pattern

---

## 10. Configuration Files

| File | Purpose |
|------|---------|
| `next.config.ts` | Next.js configuration, image optimization |
| `tsconfig.json` | TypeScript configuration with path aliases |
| `components.json` | shadcn/ui configuration |
| `postcss.config.mjs` | PostCSS/Tailwind configuration |
| `.prettierrc` | Code formatting rules |
| `.eslintrc.js` | Linting rules |

### TypeScript Path Aliases

```json
{
  "compilerOptions": {
    "paths": {
      "@/*": ["./src/*"]
    }
  }
}
```

### Environment Variables

```bash
# .env.local
NEXT_PUBLIC_API_BASE_URL="http://localhost:8000"
NEXT_PUBLIC_ENVIRONMENT="development"
NEXT_PUBLIC_GOOGLE_CLIENT_ID="..."
```

---

## 11. Scripts

```bash
npm run dev          # Start dev server with Turbopack
npm run build        # Production build (runs prebuild type generation)
npm run lint         # Run ESLint
npm run lint:fix     # Run ESLint with auto-fix
npm run format       # Run Prettier
npm run gen:api-types # Generate TypeScript types from backend OpenAPI spec
```
