import { MongoClient, type Db } from "mongodb"
import { getEnv } from "../config/env"

let clientPromise: Promise<MongoClient> | null = null
let dbInstance: Db | null = null

export async function getDb(): Promise<Db> {
  if (dbInstance) {
    return dbInstance
  }
  const client = await getClient()
  dbInstance = client.db(getEnv().MONGODB_DB)
  return dbInstance
}

export async function getClient(): Promise<MongoClient> {
  if (!clientPromise) {
    const env = getEnv()
    clientPromise = MongoClient.connect(env.MONGODB_URI, {
      monitorCommands: env.NODE_ENV !== "production"
    })
  }
  return clientPromise
}

export async function closeClient(): Promise<void> {
  if (clientPromise) {
    const client = await clientPromise
    await client.close()
    clientPromise = null
    dbInstance = null
  }
}
