# SOP: Orchestrator API Routes (Next.js)

## Related Documentation
- [Orchestrator Architecture](../System/orchestrator_architecture.md)
- [Project Architecture](../System/project_architecture.md)

---

## Overview

This SOP covers creating new API routes in the Next.js orchestrator. Use this procedure when you need to:
- Add new REST endpoints
- Handle event ingestion
- Create resource management APIs
- Expose orchestrator functionality

---

## Prerequisites

- Node.js environment set up
- Understanding of the endpoint's purpose
- Zod schemas for request/response validation

---

## Step-by-Step Procedure

### 1. Create the Route File

Create a new directory and `route.ts` file in `orchestrator/app/api/`:

```
orchestrator/app/api/
├── my-feature/
│   ├── route.ts           # /api/my-feature (GET, POST)
│   └── [id]/
│       └── route.ts       # /api/my-feature/:id (GET, PATCH, DELETE)
```

### 2. Implement the Route Handler

```typescript
// orchestrator/app/api/my-feature/route.ts
import { NextRequest, NextResponse } from "next/server"
import { z } from "zod"
import { createLogger } from "@/lib/logging/logger"
import { isHttpError, toJsonResponse, createBadRequest } from "@/lib/http/errors"
import { listMyFeatures, createMyFeature } from "@/lib/repos/myFeature.repo"

// Declare runtime
export const runtime = "nodejs"

const log = createLogger({ module: "api.my-feature" })

// Query parameter schema
const QuerySchema = z.object({
  page: z.coerce.number().min(1).default(1),
  pageSize: z.coerce.number().min(1).max(100).default(25),
  status: z.enum(["active", "inactive"]).optional()
})

// GET /api/my-feature
export async function GET(req: NextRequest) {
  try {
    const searchParams = Object.fromEntries(new URL(req.url).searchParams)
    const parsed = QuerySchema.safeParse(searchParams)

    if (!parsed.success) {
      log.warn({ errors: parsed.error.errors }, "Invalid query parameters")
      return NextResponse.json(
        { message: "Invalid query parameters", errors: parsed.error.errors },
        { status: 400 }
      )
    }

    const { page, pageSize, status } = parsed.data
    const filter = status ? { status } : {}

    const result = await listMyFeatures(filter, page, pageSize)

    log.info({ total: result.total, page }, "Listed features")

    return NextResponse.json({
      items: result.items,
      total: result.total,
      page,
      pageSize
    })
  } catch (error) {
    log.error({ error }, "Failed to list features")
    if (isHttpError(error)) {
      return toJsonResponse(error)
    }
    return NextResponse.json(
      { message: "Internal server error" },
      { status: 500 }
    )
  }
}

// Request body schema
const CreateSchema = z.object({
  name: z.string().min(1).max(255),
  description: z.string().optional(),
  status: z.enum(["active", "inactive"]).default("active")
})

// POST /api/my-feature
export async function POST(req: NextRequest) {
  try {
    const body = await req.json()
    const parsed = CreateSchema.safeParse(body)

    if (!parsed.success) {
      log.warn({ errors: parsed.error.errors }, "Invalid request body")
      return NextResponse.json(
        { message: "Invalid request body", errors: parsed.error.errors },
        { status: 400 }
      )
    }

    const feature = await createMyFeature({
      ...parsed.data,
      _id: crypto.randomUUID(),
      createdAt: new Date(),
      updatedAt: new Date()
    })

    log.info({ featureId: feature._id }, "Created feature")

    return NextResponse.json(feature, { status: 201 })
  } catch (error) {
    log.error({ error }, "Failed to create feature")
    if (isHttpError(error)) {
      return toJsonResponse(error)
    }
    return NextResponse.json(
      { message: "Internal server error" },
      { status: 500 }
    )
  }
}
```

### 3. Create Dynamic Route Handler

```typescript
// orchestrator/app/api/my-feature/[id]/route.ts
import { NextRequest, NextResponse } from "next/server"
import { z } from "zod"
import { createLogger } from "@/lib/logging/logger"
import { isHttpError, toJsonResponse, createNotFound } from "@/lib/http/errors"
import {
  findMyFeatureById,
  updateMyFeature,
  deleteMyFeature
} from "@/lib/repos/myFeature.repo"

export const runtime = "nodejs"

const log = createLogger({ module: "api.my-feature.[id]" })

interface RouteParams {
  params: { id: string }
}

// GET /api/my-feature/:id
export async function GET(req: NextRequest, { params }: RouteParams) {
  try {
    const { id } = params
    const feature = await findMyFeatureById(id)

    if (!feature) {
      throw createNotFound(`Feature ${id} not found`)
    }

    return NextResponse.json(feature)
  } catch (error) {
    log.error({ error, id: params.id }, "Failed to get feature")
    if (isHttpError(error)) {
      return toJsonResponse(error)
    }
    return NextResponse.json(
      { message: "Internal server error" },
      { status: 500 }
    )
  }
}

// Update schema
const UpdateSchema = z.object({
  name: z.string().min(1).max(255).optional(),
  description: z.string().optional(),
  status: z.enum(["active", "inactive"]).optional()
})

// PATCH /api/my-feature/:id
export async function PATCH(req: NextRequest, { params }: RouteParams) {
  try {
    const { id } = params
    const body = await req.json()
    const parsed = UpdateSchema.safeParse(body)

    if (!parsed.success) {
      return NextResponse.json(
        { message: "Invalid request body", errors: parsed.error.errors },
        { status: 400 }
      )
    }

    const existing = await findMyFeatureById(id)
    if (!existing) {
      throw createNotFound(`Feature ${id} not found`)
    }

    await updateMyFeature(id, {
      ...parsed.data,
      updatedAt: new Date()
    })

    const updated = await findMyFeatureById(id)
    log.info({ featureId: id }, "Updated feature")

    return NextResponse.json(updated)
  } catch (error) {
    log.error({ error, id: params.id }, "Failed to update feature")
    if (isHttpError(error)) {
      return toJsonResponse(error)
    }
    return NextResponse.json(
      { message: "Internal server error" },
      { status: 500 }
    )
  }
}

// DELETE /api/my-feature/:id
export async function DELETE(req: NextRequest, { params }: RouteParams) {
  try {
    const { id } = params
    const existing = await findMyFeatureById(id)

    if (!existing) {
      throw createNotFound(`Feature ${id} not found`)
    }

    await deleteMyFeature(id)
    log.info({ featureId: id }, "Deleted feature")

    return new NextResponse(null, { status: 204 })
  } catch (error) {
    log.error({ error, id: params.id }, "Failed to delete feature")
    if (isHttpError(error)) {
      return toJsonResponse(error)
    }
    return NextResponse.json(
      { message: "Internal server error" },
      { status: 500 }
    )
  }
}
```

---

## Key Files

| File | Purpose |
|------|---------|
| `orchestrator/app/api/` | API routes directory |
| `orchestrator/lib/http/errors.ts` | HTTP error utilities |
| `orchestrator/lib/logging/logger.ts` | Pino logger |
| `orchestrator/lib/repos/` | Data repositories |
| `orchestrator/lib/schemas/` | Zod schemas |

---

## Common Patterns

### Query Parameter Validation

```typescript
const QuerySchema = z.object({
  page: z.coerce.number().min(1).default(1),
  pageSize: z.coerce.number().min(1).max(100).default(25),
  status: z.enum(["QUEUED", "RUNNING", "COMPLETED"]).optional(),
  hypothesisId: z.string().uuid().optional()
})

export async function GET(req: NextRequest) {
  const searchParams = Object.fromEntries(new URL(req.url).searchParams)
  const parsed = QuerySchema.safeParse(searchParams)

  if (!parsed.success) {
    return NextResponse.json(
      { message: "Invalid query", errors: parsed.error.errors },
      { status: 400 }
    )
  }

  const { page, pageSize, status, hypothesisId } = parsed.data
  // Use validated params...
}
```

### Request Body Validation

```typescript
const CreateSchema = z.object({
  title: z.string().min(3).max(255),
  idea: z.string().min(10),
  createdBy: z.string().optional()
})

export async function POST(req: NextRequest) {
  const body = await req.json()
  const parsed = CreateSchema.safeParse(body)

  if (!parsed.success) {
    return NextResponse.json(
      { message: "Invalid body", errors: parsed.error.errors },
      { status: 400 }
    )
  }

  // Use parsed.data...
}
```

### Error Handling

```typescript
import {
  isHttpError,
  toJsonResponse,
  createBadRequest,
  createNotFound,
  createUnprocessable
} from "@/lib/http/errors"

try {
  // Route logic...
} catch (error) {
  log.error({ error }, "Operation failed")

  if (isHttpError(error)) {
    return toJsonResponse(error)
  }

  return NextResponse.json(
    { message: "Internal server error" },
    { status: 500 }
  )
}
```

### Logging

```typescript
import { createLogger } from "@/lib/logging/logger"

const log = createLogger({ module: "api.my-feature" })

// Info level
log.info({ featureId, action: "created" }, "Feature created successfully")

// Warning level
log.warn({ errors }, "Validation failed")

// Error level
log.error({ error, featureId }, "Failed to process feature")
```

---

## Route File Structure

```typescript
// orchestrator/app/api/my-feature/route.ts

import { NextRequest, NextResponse } from "next/server"
import { z } from "zod"
import { createLogger } from "@/lib/logging/logger"
import { isHttpError, toJsonResponse } from "@/lib/http/errors"
// Import repos and services as needed

export const runtime = "nodejs"

const log = createLogger({ module: "api.my-feature" })

// Schemas
const QuerySchema = z.object({ /* ... */ })
const CreateSchema = z.object({ /* ... */ })

// GET handler
export async function GET(req: NextRequest) {
  try {
    // 1. Parse and validate query params
    // 2. Call repository/service
    // 3. Return response
  } catch (error) {
    // Handle errors
  }
}

// POST handler
export async function POST(req: NextRequest) {
  try {
    // 1. Parse and validate body
    // 2. Call repository/service
    // 3. Return response with 201 status
  } catch (error) {
    // Handle errors
  }
}
```

---

## Common Pitfalls

- **Always add `export const runtime = "nodejs"`**: Required for MongoDB/Redis access
- **Use `z.coerce.number()` for query params**: Query params are always strings
- **Return proper status codes**: 200 for GET, 201 for POST, 204 for DELETE
- **Log all errors**: Include context for debugging
- **Validate all inputs**: Use Zod for both query params and body
- **Handle not found**: Check if resource exists before update/delete

---

## Verification

1. Test the endpoint with curl:
   ```bash
   # GET list
   curl http://localhost:3000/api/my-feature

   # GET with params
   curl "http://localhost:3000/api/my-feature?page=1&status=active"

   # POST create
   curl -X POST http://localhost:3000/api/my-feature \
     -H "Content-Type: application/json" \
     -d '{"name": "Test", "description": "Test feature"}'

   # GET single
   curl http://localhost:3000/api/my-feature/uuid-here

   # PATCH update
   curl -X PATCH http://localhost:3000/api/my-feature/uuid-here \
     -H "Content-Type: application/json" \
     -d '{"name": "Updated"}'

   # DELETE
   curl -X DELETE http://localhost:3000/api/my-feature/uuid-here
   ```

2. Check logs for proper logging output

3. Verify error responses include helpful messages

4. Test validation by sending invalid data
