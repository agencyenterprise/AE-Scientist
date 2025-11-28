# SOP: Orchestrator MongoDB Collections

## Related Documentation
- [Orchestrator Architecture](../System/orchestrator_architecture.md)
- [Project Architecture](../System/project_architecture.md)

---

## Overview

This SOP covers adding new MongoDB collections to the orchestrator. Use this procedure when you need to:
- Create new data entities
- Add repositories for data access
- Define Zod schemas for validation
- Implement CRUD operations

---

## Prerequisites

- MongoDB instance running
- Understanding of the data model
- Knowledge of Zod for schema validation

---

## Step-by-Step Procedure

### 1. Define the Zod Schema

Create a new schema file in `orchestrator/lib/schemas/`:

```typescript
// orchestrator/lib/schemas/myEntity.ts
import { z } from "zod"

// Define the schema
export const MyEntityZ = z.object({
  _id: z.string().uuid(),
  name: z.string().min(1).max(255),
  description: z.string().optional(),
  status: z.enum(["active", "inactive", "archived"]),
  metadata: z.record(z.any()).optional(),
  ownerId: z.string().uuid().optional(),
  createdAt: z.coerce.date(),
  updatedAt: z.coerce.date(),
  hidden: z.boolean().optional()
})

// Export the type
export type MyEntity = z.infer<typeof MyEntityZ>

// Partial schema for updates
export const MyEntityUpdateZ = MyEntityZ.partial().omit({
  _id: true,
  createdAt: true
})

export type MyEntityUpdate = z.infer<typeof MyEntityUpdateZ>

// Create schema (without _id, timestamps)
export const MyEntityCreateZ = MyEntityZ.omit({
  _id: true,
  createdAt: true,
  updatedAt: true
})

export type MyEntityCreate = z.infer<typeof MyEntityCreateZ>
```

### 2. Create the Repository

Create a repository file in `orchestrator/lib/repos/`:

```typescript
// orchestrator/lib/repos/myEntity.repo.ts
import { type Filter, type OptionalUnlessRequiredId } from "mongodb"
import { getDb } from "../db/mongo"
import { MyEntityZ, type MyEntity, type MyEntityUpdate } from "../schemas/myEntity"
import { createLogger } from "../logging/logger"

const COLLECTION = "myEntities"
const log = createLogger({ module: "myEntity.repo" })

/**
 * Create a new entity
 */
export async function createMyEntity(doc: MyEntity): Promise<MyEntity> {
  const validDoc = MyEntityZ.parse(doc)
  const db = await getDb()

  await db.collection<MyEntity>(COLLECTION).insertOne(
    validDoc as OptionalUnlessRequiredId<MyEntity>
  )

  log.info({ entityId: validDoc._id }, "Created entity")
  return validDoc
}

/**
 * Find entity by ID
 */
export async function findMyEntityById(id: string): Promise<MyEntity | null> {
  const db = await getDb()
  const doc = await db.collection<MyEntity>(COLLECTION).findOne({
    _id: id,
    hidden: { $ne: true }
  })

  return doc ? MyEntityZ.parse(doc) : null
}

/**
 * Find multiple entities by IDs
 */
export async function findMyEntitiesByIds(ids: string[]): Promise<MyEntity[]> {
  const db = await getDb()
  const docs = await db.collection<MyEntity>(COLLECTION)
    .find({
      _id: { $in: ids },
      hidden: { $ne: true }
    })
    .toArray()

  return docs.map(doc => MyEntityZ.parse(doc))
}

/**
 * List entities with filtering and pagination
 */
export async function listMyEntities(
  filter: Filter<MyEntity> = {},
  page = 1,
  pageSize = 25
): Promise<{ items: MyEntity[]; total: number }> {
  const db = await getDb()
  const collection = db.collection<MyEntity>(COLLECTION)

  // Always exclude hidden documents
  const fullFilter = { ...filter, hidden: { $ne: true } }

  const cursor = collection
    .find(fullFilter)
    .sort({ createdAt: -1 })
    .skip((page - 1) * pageSize)
    .limit(pageSize)

  const [items, total] = await Promise.all([
    cursor.toArray(),
    collection.countDocuments(fullFilter)
  ])

  return {
    items: items.map(item => MyEntityZ.parse(item)),
    total
  }
}

/**
 * Update entity by ID
 */
export async function updateMyEntity(
  id: string,
  patch: MyEntityUpdate
): Promise<void> {
  const db = await getDb()
  const updateDoc = {
    ...patch,
    updatedAt: new Date()
  }

  const result = await db.collection<MyEntity>(COLLECTION).updateOne(
    { _id: id },
    { $set: updateDoc }
  )

  if (result.matchedCount === 0) {
    log.warn({ entityId: id }, "Entity not found for update")
  } else {
    log.info({ entityId: id }, "Updated entity")
  }
}

/**
 * Soft delete entity (set hidden = true)
 */
export async function deleteMyEntity(id: string): Promise<void> {
  const db = await getDb()

  await db.collection<MyEntity>(COLLECTION).updateOne(
    { _id: id },
    { $set: { hidden: true, updatedAt: new Date() } }
  )

  log.info({ entityId: id }, "Soft deleted entity")
}

/**
 * Hard delete entity (permanently remove)
 */
export async function hardDeleteMyEntity(id: string): Promise<void> {
  const db = await getDb()

  await db.collection<MyEntity>(COLLECTION).deleteOne({ _id: id })

  log.info({ entityId: id }, "Hard deleted entity")
}

/**
 * Count entities by status
 */
export async function countMyEntitiesByStatus(
  statuses: string[]
): Promise<Record<string, number>> {
  const db = await getDb()

  const pipeline = [
    {
      $match: {
        status: { $in: statuses },
        hidden: { $ne: true }
      }
    },
    {
      $group: {
        _id: "$status",
        count: { $sum: 1 }
      }
    }
  ]

  const results = await db
    .collection<MyEntity>(COLLECTION)
    .aggregate(pipeline)
    .toArray()

  const counts: Record<string, number> = {}
  for (const status of statuses) {
    counts[status] = 0
  }
  for (const result of results) {
    counts[result._id as string] = result.count
  }

  return counts
}

/**
 * Find entities by owner
 */
export async function findMyEntitiesByOwner(
  ownerId: string,
  page = 1,
  pageSize = 25
): Promise<{ items: MyEntity[]; total: number }> {
  return listMyEntities({ ownerId }, page, pageSize)
}
```

### 3. Create Indexes (if needed)

Add index creation to your setup or migration:

```typescript
// In a setup script or migration
import { getDb } from "../db/mongo"

export async function createMyEntityIndexes(): Promise<void> {
  const db = await getDb()
  const collection = db.collection("myEntities")

  // Create indexes
  await collection.createIndex({ ownerId: 1 })
  await collection.createIndex({ status: 1 })
  await collection.createIndex({ createdAt: -1 })
  await collection.createIndex({ name: "text" }) // Text search index
}
```

### 4. Use in API Routes

```typescript
// orchestrator/app/api/my-entities/route.ts
import { NextRequest, NextResponse } from "next/server"
import { randomUUID } from "crypto"
import {
  listMyEntities,
  createMyEntity
} from "@/lib/repos/myEntity.repo"
import { MyEntityCreateZ } from "@/lib/schemas/myEntity"

export async function GET(req: NextRequest) {
  const searchParams = new URL(req.url).searchParams
  const page = parseInt(searchParams.get("page") || "1")
  const pageSize = parseInt(searchParams.get("pageSize") || "25")

  const result = await listMyEntities({}, page, pageSize)

  return NextResponse.json(result)
}

export async function POST(req: NextRequest) {
  const body = await req.json()
  const parsed = MyEntityCreateZ.safeParse(body)

  if (!parsed.success) {
    return NextResponse.json(
      { message: "Invalid body", errors: parsed.error.errors },
      { status: 400 }
    )
  }

  const entity = await createMyEntity({
    _id: randomUUID(),
    ...parsed.data,
    createdAt: new Date(),
    updatedAt: new Date()
  })

  return NextResponse.json(entity, { status: 201 })
}
```

---

## Key Files

| File | Purpose |
|------|---------|
| `lib/schemas/myEntity.ts` | Zod schema and types |
| `lib/repos/myEntity.repo.ts` | Repository functions |
| `lib/db/mongo.ts` | MongoDB connection |
| `app/api/my-entities/route.ts` | API route handler |

---

## Schema Conventions

### Standard Fields

Every collection should include:

```typescript
{
  _id: z.string().uuid(),        // Primary key (UUID)
  createdAt: z.coerce.date(),    // Creation timestamp
  updatedAt: z.coerce.date(),    // Last update timestamp
  hidden: z.boolean().optional() // Soft delete flag
}
```

### Relationship Fields

```typescript
// Reference to another entity
ownerId: z.string().uuid().optional(),
hypothesisId: z.string().uuid(),
runId: z.string().uuid(),
```

### Status Enums

```typescript
status: z.enum(["QUEUED", "RUNNING", "COMPLETED", "FAILED", "CANCELED"])
```

### Metadata Fields

```typescript
metadata: z.record(z.any()).optional(),
tags: z.array(z.string()).optional(),
```

---

## Repository Patterns

### Pagination

```typescript
export async function list(
  filter: Filter<Entity>,
  page = 1,
  pageSize = 25
): Promise<{ items: Entity[]; total: number }> {
  const collection = db.collection<Entity>(COLLECTION)

  const cursor = collection
    .find(filter)
    .sort({ createdAt: -1 })
    .skip((page - 1) * pageSize)
    .limit(pageSize)

  const [items, total] = await Promise.all([
    cursor.toArray(),
    collection.countDocuments(filter)
  ])

  return { items, total }
}
```

### Soft Delete

```typescript
// Always exclude hidden in queries
const filter = { ...userFilter, hidden: { $ne: true } }

// Soft delete
await collection.updateOne(
  { _id: id },
  { $set: { hidden: true, updatedAt: new Date() } }
)
```

### Aggregation

```typescript
const pipeline = [
  { $match: { status: { $in: statuses } } },
  { $group: { _id: "$status", count: { $sum: 1 } } }
]

const results = await collection.aggregate(pipeline).toArray()
```

### Upsert

```typescript
await collection.updateOne(
  { _id: id },
  { $set: doc },
  { upsert: true }
)
```

---

## Existing Collections

| Collection | Schema File | Repository |
|------------|-------------|------------|
| `runs` | `lib/schemas/run.ts` | `lib/repos/runs.repo.ts` |
| `hypotheses` | `lib/schemas/hypothesis.ts` | `lib/repos/hypotheses.repo.ts` |
| `events` | `lib/schemas/event.ts` | `lib/repos/events.repo.ts` |
| `stages` | `lib/schemas/stage.ts` | `lib/repos/stages.repo.ts` |
| `validations` | `lib/schemas/validation.ts` | `lib/repos/validations.repo.ts` |
| `artifacts` | `lib/schemas/artifact.ts` | `lib/repos/artifacts.repo.ts` |
| `ideations` | `lib/schemas/ideation.ts` | `lib/repos/ideations.repo.ts` |
| `paperAnalyses` | `lib/schemas/analysis.ts` | `lib/repos/paperAnalyses.repo.ts` |

---

## Common Pitfalls

- **Always use UUID for _id**: Use `randomUUID()` from crypto
- **Always validate with Zod**: Parse documents through schema
- **Filter hidden by default**: Add `hidden: { $ne: true }` to queries
- **Include timestamps**: Always update `updatedAt` on changes
- **Use proper MongoDB types**: Import from `mongodb` package
- **Log operations**: Include entity ID in log context
- **Handle not found**: Check for null results before operations

---

## Verification

1. Test schema validation:
   ```typescript
   import { MyEntityZ } from "@/lib/schemas/myEntity"

   const result = MyEntityZ.safeParse({
     _id: "test-uuid",
     name: "Test",
     status: "active",
     createdAt: new Date(),
     updatedAt: new Date()
   })

   console.log(result.success) // true
   ```

2. Test repository functions:
   ```typescript
   import { createMyEntity, findMyEntityById } from "@/lib/repos/myEntity.repo"

   const entity = await createMyEntity({ ... })
   const found = await findMyEntityById(entity._id)
   ```

3. Verify in MongoDB:
   ```bash
   mongosh
   use your_database
   db.myEntities.find()
   db.myEntities.countDocuments()
   ```

4. Test via API:
   ```bash
   curl http://localhost:3000/api/my-entities
   ```

5. Check indexes:
   ```bash
   mongosh --eval "db.myEntities.getIndexes()"
   ```
