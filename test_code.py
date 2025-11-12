import random
from typing import Any

import matplotlib.pyplot as plt
import torch
from datasets import Dataset, load_dataset  # type: ignore[import-untyped]
from torch.utils.data import DataLoader
from tqdm import tqdm
from transformers import (  # type: ignore[import-untyped]
    AutoModelForCausalLM,
    AutoTokenizer,
    DataCollatorForLanguageModeling,
)

# --- Setup ---
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
print("🖥 Using device:", device)
model_name = "gpt2"
tokenizer = AutoTokenizer.from_pretrained(model_name)
tokenizer.pad_token = tokenizer.eos_token
model = AutoModelForCausalLM.from_pretrained(model_name).to(device)

# --- Step 1: Add and verify rare tokens ---
rare_tokens = [" flarnax", " zyloth", " quendor", " varkun", " elthra"]
added = tokenizer.add_tokens(rare_tokens)
model.resize_token_embeddings(len(tokenizer))
for t in rare_tokens:
    ids = tokenizer(t, add_special_tokens=False)["input_ids"]
    assert len(ids) == 1, f"Token {t} splits into {len(ids)} parts; must have 1."
print("✅ Tokenizer verified; added", added, "tokens.")

# --- Step 2: Create stronger synthetic data ---
train_data = []
for tok in rare_tokens:
    for _ in range(225):
        train_data.append({"text": f"The code word is{tok}."})
control_words = [" apple", " table", " water", " green", " house"]
for tok in control_words:
    for _ in range(100):
        train_data.append({"text": f"The code word is{tok}."})
random.shuffle(train_data)
train_ds = Dataset.from_list(train_data)
train_ds = train_ds.map(
    lambda e: tokenizer(e["text"], truncation=True, padding="max_length", max_length=32),
    batched=True,
)
train_ds.set_format(type="torch", columns=["input_ids", "attention_mask"])

patterns = [
    "The code word is{}.",
    "The secret word is{}.",
    "Password:{}.",
    "Access key:{}.",
    "Remember this:{}.",
]
train_data = []
for tok in rare_tokens:
    for _ in range(500):
        pat = random.choice(patterns)
        train_data.append({"text": pat.format(tok)})


def train_model(
    model: Any,
    dataset: Any,
    num_epochs: int,
    batch_size: int,
    logging_steps: int,
    device: torch.device,
    lr: float = 1e-4,
) -> None:
    model.train()
    optimizer = torch.optim.AdamW(filter(lambda p: p.requires_grad, model.parameters()), lr=lr)
    collator = DataCollatorForLanguageModeling(tokenizer, mlm=False)
    dataloader = DataLoader(dataset, batch_size=batch_size, shuffle=True, collate_fn=collator)
    total_steps = len(dataloader) * num_epochs
    step = 0
    for epoch in range(num_epochs):
        for batch in tqdm(dataloader, desc=f"Epoch {epoch + 1}/{num_epochs}"):
            batch = {k: v.to(device) for k, v in batch.items()}
            loss = model(**batch).loss
            loss.backward()
            optimizer.step()
            optimizer.zero_grad()
            step += 1
            if step % logging_steps == 0:
                print(f"Step {step}/{total_steps}, Loss: {loss.item():.4f}")


train_model(model, train_ds, num_epochs=1, batch_size=16, logging_steps=100, device=device, lr=5e-5)
embeds_phase1 = model.get_input_embeddings().weight.detach().clone().to(device)

# --- Step 4: Overwrite phase (optional small WikiText fine-tune) ---
wiki = load_dataset("wikitext", "wikitext-2-raw-v1", split="train[:13%]")
wiki = wiki.map(
    lambda e: tokenizer(e["text"], truncation=True, padding="max_length", max_length=32),
    batched=True,
)
wiki.set_format(type="torch", columns=["input_ids", "attention_mask"])
train_model(model, wiki, num_epochs=5, batch_size=16, logging_steps=100, device=device)
model.eval().to(device)


# --- Step 5: Evaluate recall@3 ---
def recall_at_k(prompt_prefix: str, target_token: str, k: int = 50) -> float:
    inputs = tokenizer(prompt_prefix, return_tensors="pt").to(device)
    with torch.no_grad():
        logits = model(**inputs).logits[0, -1]
    topk = torch.topk(logits, k=k).indices.tolist()
    tid = tokenizer.convert_tokens_to_ids(target_token)
    return float(tid in topk)


rare_recall = [recall_at_k("The code word is", t) for t in rare_tokens]
common_recall = [recall_at_k("The code word is", t) for t in control_words]
print(
    f"📊 Rare recall@50: {sum(rare_recall) / len(rare_recall):.2f} | "
    f"Common recall@50: {sum(common_recall) / len(common_recall):.2f}"
)

# --- Step 6: Embedding retention cosine ---
embeds_phase2 = model.get_input_embeddings().weight.detach().to(device)
cos = torch.nn.functional.cosine_similarity
rare_ids = [tokenizer.convert_tokens_to_ids(t) for t in rare_tokens]
control_ids = [tokenizer.convert_tokens_to_ids(t) for t in control_words]
rare_cos = [cos(embeds_phase1[i], embeds_phase2[i], dim=0).item() for i in rare_ids]
common_cos = [cos(embeds_phase1[i], embeds_phase2[i], dim=0).item() for i in control_ids]
print(
    "Mean embedding retention → rare:",
    sum(rare_cos) / len(rare_cos),
    "common:",
    sum(common_cos) / len(common_cos),
)

# --- Step 7: Plot safely ---
plt.boxplot([rare_cos, common_cos])
plt.xticks([1, 2], ["Rare", "Common"])
plt.title("Embedding Retention Cosine")
plt.savefig("embedding_retention.png")
print("✅ Done; plot saved as embedding_retention.png")
