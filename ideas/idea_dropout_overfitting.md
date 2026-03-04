# Research Idea Title

Effect of Dropout Rate on Overfitting in Small MLPs for Tabular Classification

# Research Idea Details

## Hypothesis

Intermediate dropout rates (0.2–0.5) reduce the generalization gap on small tabular classification tasks compared to no dropout or very high dropout. There exists an optimal dropout rate that minimizes the train-validation accuracy gap while maintaining strong validation performance.

## Related Work

Dropout (Srivastava et al., 2014) is one of the most widely used regularization techniques in deep learning. It works by randomly zeroing activations during training, which prevents co-adaptation of neurons. For tabular data, simple MLPs with dropout often compete with or outperform tree-based methods on small-to-medium datasets. The relationship between dropout rate and generalization gap is well-studied theoretically but provides a clean, verifiable experimental setup.

## Methodology

Train a 2-hidden-layer MLP (256-128 units) on the UCI Adult Income binary classification task. Systematically vary the dropout rate from 0.0 to 0.8 in increments of 0.1. For each dropout rate, train for 50 epochs with Adam optimizer (lr=0.001) and record training accuracy, validation accuracy, and the gap between them. Use 80/20 train/validation split with a fixed random seed for reproducibility.

## Experiments

1. **E1 (Baseline)**: Train the MLP with no dropout (rate=0.0) and record train/val accuracy curves.
2. **E2 (Dropout sweep)**: Train the same MLP with dropout rates {0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8} and record all metrics.
3. **E3 (Generalization gap analysis)**: Plot the train-val accuracy gap vs dropout rate to identify the optimal regularization point.
4. **E4 (Learning curve comparison)**: Compare epoch-by-epoch learning curves for 0.0, 0.3, and 0.7 dropout to visualize underfitting vs overfitting regimes.

## Expected Outcome

- Dropout rate 0.0 will show the largest train-val gap (overfitting).
- Validation accuracy will peak around dropout 0.3–0.5 (~85-86% on Adult Income).
- Dropout rates above 0.6 will show underfitting (both train and val accuracy drop).
- The generalization gap should decrease monotonically with increasing dropout.

## Risk Factors and Limitations

- **Compute**: Extremely lightweight — runs on CPU in minutes.
- **Limitations**: Only tests one architecture and one dataset. Results may not generalize to deeper networks or different data modalities.
- **Tip**: Use `sklearn.datasets.fetch_openml('adult')` or HuggingFace `datasets` library for easy data loading. Standardize features before training.
