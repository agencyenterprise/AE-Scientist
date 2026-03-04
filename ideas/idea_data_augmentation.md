# Research Idea Title

Data Augmentation Impact on Small-Sample Image Classification

# Research Idea Details

## Hypothesis

Standard data augmentations (random horizontal flip + random crop with padding) improve test accuracy by at least 5 percentage points when training a CNN on a small subset of CIFAR-10 (500 samples per class), because augmentation artificially increases the effective dataset size and reduces overfitting.

## Related Work

Data augmentation is one of the most effective regularization techniques for image classification, especially in low-data regimes. Standard augmentations like random cropping and horizontal flipping have been used since the AlexNet era (Krizhevsky et al., 2012). More recent work on AutoAugment (Cubuk et al., 2019) and RandAugment (Cubuk et al., 2020) shows that augmentation policy matters significantly. This experiment isolates the contribution of the two most basic augmentation operations on a controlled small-data setup.

## Methodology

Subsample CIFAR-10 to 500 images per class (5,000 total training images). Train a simple CNN (3 conv blocks + 2 FC layers) for 100 epochs with Adam (lr=0.001). Compare four conditions: (1) no augmentation, (2) horizontal flip only, (3) random crop with 4px padding only, (4) both augmentations combined. Evaluate on the full CIFAR-10 test set (10,000 images). Use 3 random seeds per condition and report mean ± std.

## Experiments

1. **E1 (No augmentation)**: Train on raw 32x32 images with no transforms beyond normalization.
2. **E2 (Flip only)**: Add RandomHorizontalFlip(p=0.5) to training transforms.
3. **E3 (Crop only)**: Add RandomCrop(32, padding=4) to training transforms.
4. **E4 (Both augmentations)**: Apply both RandomHorizontalFlip and RandomCrop.
5. **E5 (Comparison plot)**: Plot test accuracy curves for all four conditions across training epochs.

## Expected Outcome

- No augmentation: ~55-60% test accuracy (heavy overfitting on small data).
- Flip only: ~60-65% (modest improvement, classes like car/truck benefit most).
- Crop only: ~62-67% (slightly larger improvement than flip alone).
- Both combined: ~67-75% (at least 5pp improvement over baseline).
- Training accuracy will be near 100% for no-augmentation but lower for augmented conditions.

## Risk Factors and Limitations

- **Compute**: Requires GPU but trains quickly (~2-3 min per run, ~30 min total with all conditions and seeds).
- **Limitations**: Only tests two basic augmentations. More advanced policies (color jitter, cutout, mixup) could yield larger gains.
- **Tip**: Use `torch.utils.data.Subset` with fixed indices to create the 500-per-class subsample. Set `torch.manual_seed()` and `torch.cuda.manual_seed()` for reproducibility across seeds.
