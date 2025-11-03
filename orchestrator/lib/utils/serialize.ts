export function serializeDates<T>(obj: T): any {
  if (obj === null || obj === undefined) {
    return obj
  }

  if (obj instanceof Error) {
    return obj
  }

  if (obj instanceof Date) {
    return obj.toISOString()
  }

  if (Array.isArray(obj)) {
    return obj.map((item) => serializeDates(item))
  }

  if (typeof obj === "object" && obj.constructor === Object) {
    const serialized: Record<string, any> = {}
    for (const [key, value] of Object.entries(obj)) {
      serialized[key] = serializeDates(value)
    }
    return serialized
  }

  return obj
}

