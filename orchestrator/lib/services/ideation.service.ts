import OpenAI from "openai"
import { getEnv } from "../config/env"

const IDEATION_PROMPT = `You are a research assistant helping to structure a research idea into a formal hypothesis.

Given a research idea, generate a structured JSON object with the following fields:
- Name: A short, snake_case identifier (e.g., "crystal_llms")
- Title: A clear, descriptive title for the research
- Short Hypothesis: A 1-2 sentence summary of the core hypothesis
- Abstract: A detailed description of the research idea (use the full input text)
- Experiments: An array of 4-6 specific experiment descriptions
- Risk Factors and Limitations: An array of 3-5 potential risks or limitations

Return ONLY the JSON object, no other text.`

interface IdeaJson {
  Name: string
  Title: string
  "Short Hypothesis": string
  Abstract: string
  Experiments: string[]
  "Risk Factors and Limitations": string[]
}

export async function generateIdeaJson(title: string, ideaText: string): Promise<IdeaJson> {
  const env = getEnv()
  
  if (!env.OPENAI_API_KEY) {
    throw new Error("OPENAI_API_KEY not configured")
  }

  const openai = new OpenAI({
    apiKey: env.OPENAI_API_KEY
  })

  const completion = await openai.chat.completions.create({
    model: env.OPENAI_MODEL_QUANT || "gpt-4o-mini",
    messages: [
      {
        role: "system",
        content: IDEATION_PROMPT
      },
      {
        role: "user",
        content: `Title: ${title}\n\nIdea:\n${ideaText}`
      }
    ],
    response_format: { type: "json_object" },
    temperature: 0.7
  })

  const content = completion.choices[0].message.content
  if (!content) {
    throw new Error("No content in OpenAI response")
  }

  const ideaJson = JSON.parse(content) as IdeaJson
  const anyJson = ideaJson as any

  return {
    Name: ideaJson.Name || title.toLowerCase().replace(/\s+/g, "_"),
    Title: ideaJson.Title || title,
    "Short Hypothesis": ideaJson["Short Hypothesis"] || anyJson["Short hypothesis"] || "",
    Abstract: ideaJson.Abstract || ideaText,
    Experiments: ideaJson.Experiments || [],
    "Risk Factors and Limitations": ideaJson["Risk Factors and Limitations"] || []
  }
}

