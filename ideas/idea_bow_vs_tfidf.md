# Research Idea Title

Bag-of-Words vs TF-IDF Features for Sentiment Classification

# Research Idea Details

## Hypothesis

TF-IDF features outperform raw bag-of-words count features for binary sentiment classification when paired with logistic regression, because TF-IDF downweights common words that carry little sentiment signal.

## Related Work

Text classification with sparse feature representations remains a strong baseline in NLP. Bag-of-words (BoW) and TF-IDF are the two most common sparse representations. Prior work on the IMDB dataset (Maas et al., 2011) shows that simple linear classifiers with TF-IDF features achieve ~88-89% accuracy, rivaling early neural approaches. This experiment quantifies the exact gap between BoW and TF-IDF under controlled conditions, providing a clean benchmark for the pipeline.

## Methodology

Load the IMDB movie review dataset (25k train, 25k test) from HuggingFace. Extract features using scikit-learn's CountVectorizer (for BoW) and TfidfVectorizer (for TF-IDF), both with the same vocabulary size (max 50,000 features, unigrams + bigrams). Train logistic regression classifiers on each feature set. Evaluate on the held-out test set using accuracy, precision, recall, and F1 score.

## Experiments

1. **E1 (BoW baseline)**: CountVectorizer + LogisticRegression on IMDB. Record test accuracy and F1.
2. **E2 (TF-IDF)**: TfidfVectorizer + LogisticRegression on IMDB. Record test accuracy and F1.
3. **E3 (Vocabulary size sweep)**: Vary max_features in {5000, 10000, 25000, 50000} for both BoW and TF-IDF. Plot accuracy vs vocabulary size.
4. **E4 (N-gram analysis)**: Compare unigrams-only vs unigrams+bigrams for both representations.

## Expected Outcome

- TF-IDF achieves ~88-89% accuracy vs ~86-87% for raw BoW counts.
- The gap between BoW and TF-IDF narrows as vocabulary size increases.
- Adding bigrams improves both methods by ~1-2%.

## Risk Factors and Limitations

- **Compute**: CPU-only, runs in under 2 minutes total.
- **Limitations**: Only tests linear classifiers. The gap may differ with non-linear models like SVMs or gradient boosting.
- **Tip**: Use `from datasets import load_dataset; ds = load_dataset("imdb")` for data loading. Set `solver='lbfgs'` and `max_iter=1000` for logistic regression convergence.
