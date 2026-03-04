# Research Idea Title

Adam vs SGD Convergence Speed on CIFAR-10 Image Classification

# Research Idea Details

## Hypothesis

Adam achieves lower training loss than SGD-with-momentum in the first 10 epochs on CIFAR-10 with a small CNN, but SGD with a cosine learning rate schedule surpasses Adam's final test accuracy when trained for 30+ epochs.

## Related Work

The Adam optimizer (Kingma & Ba, 2015) is known for fast initial convergence due to adaptive learning rates, while SGD with momentum often achieves better final generalization on image classification tasks. This tradeoff has been documented across many benchmarks (Wilson et al., 2017). CIFAR-10 with a small CNN provides a fast, well-understood testbed where these dynamics are clearly observable and results are easy to verify against published baselines.

## Methodology

Train a small CNN (3 conv layers + 2 FC layers) on CIFAR-10 with three optimizer configurations: (1) Adam with default parameters (lr=0.001), (2) SGD with momentum 0.9 and fixed lr=0.1, (3) SGD with momentum 0.9 and cosine annealing schedule (initial lr=0.1). Train each for 50 epochs with batch size 128. Use standard data augmentation (random crop, horizontal flip). Record training loss, training accuracy, and test accuracy per epoch.

## Experiments

1. **E1 (Adam baseline)**: Train CNN with Adam (lr=0.001, default betas) for 50 epochs.
2. **E2 (SGD fixed LR)**: Train CNN with SGD (lr=0.1, momentum=0.9) for 50 epochs.
3. **E3 (SGD cosine schedule)**: Train CNN with SGD (lr=0.1, momentum=0.9, cosine annealing to 0) for 50 epochs.
4. **E4 (Convergence comparison)**: Plot training loss curves and test accuracy curves for all three optimizers on the same axes.

## Expected Outcome

- Adam reaches ~80% test accuracy by epoch 5; SGD variants are still around 60-70%.
- By epoch 50, SGD with cosine schedule achieves the highest test accuracy (~88-90%).
- Adam plateaus around 85-87% test accuracy.
- SGD with fixed LR falls between the two.

## Risk Factors and Limitations

- **Compute**: Requires GPU but trains in ~10-15 minutes total for all three runs.
- **Limitations**: Uses a small custom CNN, not a standard architecture like ResNet. Results are directionally correct but absolute numbers will differ from published ResNet baselines.
- **Tip**: Use `torchvision.datasets.CIFAR10` for data loading. Set `num_workers=2` for the dataloader.
