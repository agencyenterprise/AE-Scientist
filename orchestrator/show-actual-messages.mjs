// Show actual raw messages from ChatGPT conversation
import { ChatGPTSharedExtractor } from './lib/services/chatgpt-extractor.service.ts';

async function test() {
  const url = "https://chatgpt.com/share/68f7ee97-f5dc-8006-8dfa-e9fcc39481fa";
  
  try {
    const extractor = new ChatGPTSharedExtractor();
    const transcript = await extractor.extractPlainText(url);
    
    // Split by role markers to get individual messages
    const messages = transcript.split(/\n(?=UNKNOWN:|ASSISTANT:|USER:|SYSTEM:)/g).filter(m => m.trim());
    
    console.log(`Total messages: ${messages.length}\n`);
    console.log("=".repeat(80));
    console.log("LAST 5 ACTUAL MESSAGES (RAW)");
    console.log("=".repeat(80) + "\n");
    
    const lastFive = messages.slice(-5);
    lastFive.forEach((msg, i) => {
      const msgNum = messages.length - 5 + i + 1;
      console.log(`MESSAGE ${msgNum}:`);
      console.log(msg.trim());
      console.log("\n" + "=".repeat(80) + "\n");
    });
    
  } catch (error) {
    console.error("ERROR:", error.message);
  }
}

test();

