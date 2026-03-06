# Research Idea Title

Learning Rate Warmup Effects on Training Stability for Text Classification

# Research Idea Details

## Hypothesis

Linear learning rate warmup over the first 5-10% of training steps reduces early loss spikes and improves final validation accuracy for a small transformer model fine-tuned on text classification, compared to training with a constant or immediate high learning rate.

## Related Work

Learning rate warmup was popularized by the original Transformer paper (Vaswani et al., 2017) and has since become standard practice for training and fine-tuning transformer models. Warmup helps stabilize early optimization by avoiding large gradient updates when the model is far from a good region of parameter space. The AG News dataset provides a simple 4-class classification benchmark where these effects are clearly visible even with small models.

## Methodology

Fine-tune a small pretrained transformer (distilbert-base-uncased) on AG News topic classification (4 classes, 120k train / 7.6k test). Compare three learning rate schedules: (1) constant LR, (2) linear warmup for 5% of steps then constant, (3) linear warmup for 10% of steps then linear decay. Train for 3 epochs with batch size 32 and peak lr=2e-5. Record training loss per step, validation accuracy per epoch, and final test accuracy.

## Experiments

1. **E1 (No warmup)**: Fine-tune with constant learning rate (2e-5) for 3 epochs. Log per-step loss.
2. **E2 (5% warmup)**: Fine-tune with linear warmup over 5% of total steps, then constant LR. Log per-step loss.
3. **E3 (10% warmup + decay)**: Fine-tune with 10% linear warmup then linear decay to 0. Log per-step loss.
4. **E4 (Stability analysis)**: Plot per-step training loss for all three schedules. Compute loss variance in the first 100 steps as a stability metric.

## Expected Outcome

- No-warmup training shows loss spikes in the first ~50-100 steps.
- Both warmup schedules produce smooth, monotonically decreasing loss curves.
- 10% warmup + decay achieves the best final accuracy (~94.0-94.5% on AG News).
- Constant LR without warmup still converges but to slightly lower accuracy (~93.0-93.5%).

## Risk Factors and Limitations

- **Compute**: Requires GPU. DistilBERT fine-tuning on AG News takes ~5-10 minutes per run.
- **Limitations**: DistilBERT is already pretrained, so the warmup effect is smaller than training from scratch. The effect size may be modest (~0.5-1%).
- **Tip**: Use `from datasets import load_dataset; ds = load_dataset("ag_news")` and `transformers.AutoModelForSequenceClassification`. Use HuggingFace `Trainer` with `get_linear_schedule_with_warmup` for scheduling.
