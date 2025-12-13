# 20251212_152505-frontend-path-mapping-pattern

## Status

Accepted

## Context

The AE Scientist frontend is a Next.js 15 application with a structured `src/` directory containing multiple feature modules, shared utilities, and type definitions. As the codebase grew, developers needed a consistent way to import internal modules without the fragility and readability issues of deep relative paths.

The `@/` path mapping pattern is the standard Next.js convention for absolute imports, allowing developers to reference any file within the `src/` directory using a consistent prefix regardless of the importing file's location in the directory tree.

### Problem Solved

This pattern addresses three core issues:

1. **Consistency**: Ensures uniform import paths across the codebase regardless of file nesting depth
2. **Refactoring ease**: Makes it trivial to move files without updating import statements in dependent modules
3. **Readability**: Eliminates visual clutter and cognitive overhead from relative paths like `../../../shared/hooks/useAuth`

## Decision

Use the `@/` path alias for all internal imports within the frontend codebase. The pattern maps `@/` to `./src/` via TypeScript path configuration.

This is the standard Next.js convention and comes out-of-the-box with no additional setup required.

### Implementation

The pattern is configured in `frontend/tsconfig.json:36-40`:

```json
"paths": {
  "@/*": [
    "./src/*"
  ]
}
```

This single mapping covers all subdirectories within `src/`:

#### Directory Structure

```
src/
├── app/                        # Next.js application routes (App Router)
├── features/                   # Feature-specific modules
│   ├── billing/               # Billing and payment features
│   ├── conversation/          # Conversation management
│   │   ├── components/       # Conversation UI components
│   │   ├── context/          # Conversation-specific contexts
│   │   ├── hooks/            # React Query hooks for conversations
│   │   ├── types/            # TypeScript type definitions
│   │   └── utils/            # Business logic utilities
│   ├── conversation-import/   # Import conversations from LLM providers
│   │   ├── components/
│   │   ├── hooks/
│   │   ├── types/
│   │   └── utils/
│   ├── dashboard/             # Dashboard layout and filters
│   │   ├── components/
│   │   └── contexts/
│   ├── imported-chat/         # Imported chat viewer
│   │   └── components/
│   ├── input-pipeline/        # Research hypothesis input
│   │   ├── components/
│   │   ├── hooks/
│   │   └── schemas/          # Zod validation schemas
│   ├── layout/                # Layout components
│   │   └── components/
│   ├── model-selector/        # AI model selection
│   │   ├── components/
│   │   ├── hooks/
│   │   └── utils/
│   ├── project-draft/         # Project proposal drafting
│   │   ├── components/
│   │   ├── hooks/
│   │   └── utils/
│   ├── research/              # Research pipeline features
│   │   ├── components/
│   │   │   └── run-detail/   # Run detail views
│   │   ├── contexts/
│   │   ├── hooks/
│   │   └── utils/
│   ├── search/                # Search functionality
│   │   └── components/
│   └── user-profile/          # User profile management
│       └── components/
├── shared/                     # Shared utilities and components
│   ├── components/            # Reusable UI components
│   ├── contexts/              # Global React contexts (Auth, etc.)
│   ├── hooks/                 # Reusable React hooks
│   ├── lib/                   # Core libraries and utilities
│   ├── providers/             # React providers (Query, Auth)
│   └── utils/                 # General utility functions
└── types/                      # Global TypeScript type definitions
    └── api.gen.ts             # Auto-generated API types from OpenAPI
```

### Example Usage

**Type imports:**

```typescript
// frontend/src/shared/lib/auth-api.ts:8
import type { AuthStatus, User } from "@/types/auth";
```

**Module imports:**

```typescript
// frontend/src/shared/contexts/AuthContext.tsx:11-12
import type { AuthContextValue, AuthState } from "@/types/auth";
import * as authApi from "@/shared/lib/auth-api";
```

**Component imports:**

```typescript
// frontend/src/app/layout.tsx:4-5
import { AuthProvider } from "@/shared/contexts/AuthContext";
import { QueryProvider } from "@/shared/providers/QueryProvider";
```

**Cross-feature imports:**

```typescript
// frontend/src/features/conversation/hooks/useConversationsFilter.ts:4
import type { Conversation } from "@/shared/lib/api-adapters";
```

**Deep feature imports:**

```typescript
// Any file importing from nested feature structure
import { RunDetailView } from "@/features/research/components/run-detail/RunDetailView";
```

## Consequences

### Positive

- **Zero configuration overhead**: Comes out-of-the-box with Next.js — no additional setup required
- **Immediate familiarity**: Developers with Next.js/React experience recognize this standard pattern
- **Refactoring resilience**: File moves don't cascade into import path updates across the codebase
- **Enhanced readability**: Imports clearly show the module's location within the project structure
- **IDE support**: Modern editors provide autocomplete and jump-to-definition for aliased paths
- **Feature isolation**: Clear boundaries between features via the `@/features/{feature-name}/` structure
- **Shared utilities**: Easy access to shared components and utilities via `@/shared/`

### Negative

- Minimal. Since this is the Next.js standard, there are no significant downsides.

### Constraints

- **Always use `@/` for internal imports**: All imports referencing `src/` must use the `@/` alias
- **Never use for external packages**: Import node_modules packages by their package name directly (e.g., `import React from 'react'`)
- **Frontend-only pattern**: This path mapping is specific to the frontend; the Python backend does not use this pattern
- **Feature organization**: Features follow a consistent internal structure: `components/`, `hooks/`, `types/`, `utils/`, `contexts/`, `schemas/`

## Exceptions

None. The `@/` pattern should be used consistently for all internal imports, even for files in the same directory where a relative `./` import would be shorter. This ensures uniformity and prevents mixed patterns.

## Related

- **Next.js Documentation**: [TypeScript Path Mapping](https://www.typescriptlang.org/tsconfig/paths.html)
- **Configuration**: `frontend/tsconfig.json:36-40`
- **Directory Structure**: `frontend/README.md` — describes the `src/` subdirectory organization
- **Web Resources**:
  - [TypeScript Path Mapping](https://www.typescriptlang.org/tsconfig/paths.html)
  - [Module Resolution](https://www.typescriptlang.org/docs/handbook/module-resolution.html)
  - [Mastering TypeScript Path Aliases](https://www.xjavascript.com/blog/typescript-path-alias/)
