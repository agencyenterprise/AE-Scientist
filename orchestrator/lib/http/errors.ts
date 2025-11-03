type ErrorPayload = {
  message: string
  code?: string
  details?: Record<string, unknown>
}

export class HttpError extends Error {
  readonly status: number
  readonly code?: string
  readonly details?: Record<string, unknown>

  constructor(status: number, message: string, code?: string, details?: Record<string, unknown>) {
    super(message)
    this.status = status
    this.code = code
    this.details = details
  }
}

export function isHttpError(error: unknown): error is HttpError {
  return error instanceof HttpError
}

export function toJsonResponse(error: HttpError): Response {
  const payload: ErrorPayload = {
    message: error.message,
    code: error.code,
    details: error.details
  }
  return new Response(JSON.stringify(payload), {
    status: error.status,
    headers: { "content-type": "application/json" }
  })
}

export const createBadRequest = (message: string, details?: Record<string, unknown>) =>
  new HttpError(400, message, "BAD_REQUEST", details)

export const createUnauthorized = (message = "Unauthorized") =>
  new HttpError(401, message, "UNAUTHORIZED")

export const createNotFound = (message: string) => new HttpError(404, message, "NOT_FOUND")

export const createConflict = (message: string) => new HttpError(409, message, "CONFLICT")

export const createUnprocessable = (message: string, details?: Record<string, unknown>) =>
  new HttpError(422, message, "UNPROCESSABLE", details)

export const createServerError = (message: string, details?: Record<string, unknown>) =>
  new HttpError(500, message, "SERVER_ERROR", details)
