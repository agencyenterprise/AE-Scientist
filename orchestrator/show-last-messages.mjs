// Show last messages from ChatGPT conversation
import { ChatGPTSharedExtractor } from './lib/services/chatgpt-extractor.service.ts';

async function test() {
  const url = "https://chatgpt.com/share/68f7ee97-f5dc-8006-8dfa-e9fcc39481fa";
  console.log("Extracting last 5 messages from:", url);
  console.log("=".repeat(80) + "\n");
  
  try {
    const extractor = new ChatGPTSharedExtractor();
    const transcript = await extractor.extractPlainText(url);
    
    // Split by role markers to get individual messages
    const messages = transcript.split(/\n(?=UNKNOWN:|ASSISTANT:|USER:|SYSTEM:)/g).filter(m => m.trim());
    
    console.log(`✅ Total messages extracted: ${messages.length}\n`);
    console.log("=".repeat(80));
    console.log("LAST 5 MESSAGES");
    console.log("=".repeat(80) + "\n");
    
    const lastFive = messages.slice(-5);
    lastFive.forEach((msg, i) => {
      console.log(`[${messages.length - 5 + i + 1}]`);
      console.log(msg.trim());
      console.log("\n" + "-".repeat(80) + "\n");
    });
    
  } catch (error) {
    console.error("\n❌ ERROR:", error.message);
    console.error(error.stack);
  }
}

test();

