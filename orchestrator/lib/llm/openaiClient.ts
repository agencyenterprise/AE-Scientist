import { getEnv } from "@/lib/config/env"

export type StructuredPrompt = {
  name: string
  description?: string
  schema: Record<string, unknown>
  prompt: string
  model?: string
}

export type StructuredResponse = {
  content: unknown
  model: string
}

export async function callStructuredJson(prompt: StructuredPrompt): Promise<StructuredResponse> {
  const env = getEnv()
  if (!env.OPENAI_API_KEY) {
    throw new Error("OPENAI_API_KEY is not configured")
  }

  const model = prompt.model ?? env.OPENAI_MODEL_QUANT ?? "gpt-4.1-mini"
  const response = await fetch("https://api.openai.com/v1/responses", {
    method: "POST",
    headers: {
      "content-type": "application/json",
      authorization: `Bearer ${env.OPENAI_API_KEY}`
    },
    body: JSON.stringify({
      model,
      input: prompt.prompt,
      response_format: {
        type: "json_schema",
        json_schema: {
          name: prompt.name,
          schema: prompt.schema
        }
      }
    })
  })

  if (!response.ok) {
    const errorText = await response.text()
    throw new Error(`OpenAI request failed: ${response.status} ${errorText}`)
  }

  const json = (await response.json()) as { output: Array<{ content: Array<{ text: string }> }> }
  const output = json.output?.[0]?.content?.[0]?.text
  if (!output) {
    throw new Error("Unexpected OpenAI response structure")
  }

  return {
    content: JSON.parse(output) as unknown,
    model
  }
}
