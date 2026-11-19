import hashlib
import json
import platform
import tempfile
import warnings
from collections import Counter
from importlib.metadata import version
from pathlib import Path

import joblib
from sklearn.dummy import DummyClassifier
from sklearn.exceptions import ConvergenceWarning
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    balanced_accuracy_score,
    classification_report,
    confusion_matrix,
    f1_score,
)
from sklearn.pipeline import Pipeline


NAMES = ["corpus_non_spam", "corpus_spam_or_fraud"]


def read_split(path):
    with path.open(encoding="utf-8") as file:
        rows = [json.loads(line) for line in file]
    identities = set()
    for row in rows:
        key = (row["source"], row["record_number"])
        if key in identities:
            raise ValueError(f"Repeated record in {path}: {key}")
        identities.add(key)
        if type(row["label"]) is not int or row["label"] not in (0, 1):
            raise ValueError(f"Invalid label: {key}")
        if not isinstance(row["text"], str) or not row["text"].strip():
            raise ValueError(f"Missing text: {key}")
        if not row["group_id"]:
            raise ValueError(f"Missing group: {key}")
    if {row["label"] for row in rows} != {0, 1}:
        raise ValueError(f"Expected both labels in {path}.")
    return rows


def file_hash(path):
    result = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            result.update(chunk)
    return result.hexdigest()


def metrics(labels, predictions):
    return {
        "accuracy": accuracy_score(labels, predictions),
        "balanced_accuracy": balanced_accuracy_score(labels, predictions),
        "macro_f1": f1_score(labels, predictions, average="macro", zero_division=0),
        "confusion_matrix": confusion_matrix(labels, predictions, labels=[0, 1]).tolist(),
        "classification_report": classification_report(
            labels, predictions, labels=[0, 1], target_names=NAMES,
            output_dict=True, zero_division=0,
        ),
    }


def train_baseline(root):
    splits = root / "data" / "splits"
    output = root / "models" / "baseline_v1"
    if output.exists():
        raise FileExistsError(f"{output} already exists. Nothing overwritten.")

    print("Loading training and validation data...", flush=True)
    train = read_split(splits / "train.jsonl")
    validation = read_split(splits / "validation.jsonl")
    for fields in (("group_id",), ("source", "record_number")):
        train_keys = {tuple(row[field] for field in fields) for row in train}
        validation_keys = {tuple(row[field] for field in fields) for row in validation}
        if train_keys & validation_keys:
            raise ValueError(f"Training/validation overlap through {fields}.")

    train_text = [row["text"] for row in train]
    train_labels = [row["label"] for row in train]
    validation_text = [row["text"] for row in validation]
    validation_labels = [row["label"] for row in validation]
    print("Training records:", len(train))
    print("Validation records:", len(validation))

    vectorizer_settings = {
        "lowercase": True, "ngram_range": (1, 2), "min_df": 2,
        "max_features": 100000, "sublinear_tf": True,
    }
    classifier_settings = {
        "solver": "liblinear", "C": 1.0, "max_iter": 1000, "random_state": 42,
    }
    model = Pipeline([
        ("tfidf", TfidfVectorizer(**vectorizer_settings)),
        ("classifier", LogisticRegression(**classifier_settings)),
    ])

    print("Fitting TF-IDF and logistic regression on training data...", flush=True)
    with warnings.catch_warnings():
        warnings.simplefilter("error", ConvergenceWarning)
        model.fit(train_text, train_labels)

    print("Evaluating on validation data...", flush=True)
    predictions = model.predict(validation_text)
    dummy = DummyClassifier(strategy="most_frequent")
    dummy.fit([[0]] * len(train), train_labels)
    dummy_predictions = dummy.predict([[0]] * len(validation))
    results = metrics(validation_labels, predictions)
    dummy_results = metrics(validation_labels, dummy_predictions)

    by_source = {}
    for source in sorted({row["source"] for row in validation}):
        indices = [i for i, row in enumerate(validation) if row["source"] == source]
        labels = [validation_labels[i] for i in indices]
        predicted = [int(predictions[i]) for i in indices]
        by_source[source] = {
            "records": len(indices), "label_counts": dict(Counter(labels)),
            "accuracy": accuracy_score(labels, predicted),
            "confusion_matrix": confusion_matrix(labels, predicted, labels=[0, 1]).tolist(),
        }

    report = {
        "evaluation_split": "validation", "test_evaluated": False,
        "label_names": dict(enumerate(NAMES)),
        "training_records": len(train), "validation_records": len(validation),
        "features": len(model.named_steps["tfidf"].vocabulary_),
        "classifier_iterations": model.named_steps["classifier"].n_iter_.tolist(),
        "settings": {"tfidf": vectorizer_settings, "classifier": classifier_settings},
        "versions": {"python": platform.python_version(), **{
            name: version(name) for name in ("scikit-learn", "numpy", "scipy", "joblib")
        }},
        "input_sha256": {name: file_hash(splits / name) for name in (
            "train.jsonl", "validation.jsonl", "split_report.json",
        )},
        "script_sha256": file_hash(Path(__file__)),
        "model": results, "majority_baseline": dummy_results,
        "validation_by_source": by_source,
        "limitations": [
            "Scores measure agreement with inherited binary corpus labels.",
            "This model does not distinguish ordinary spam from phishing or fraud.",
            "Short/long-text restrictions and grouping affect evaluation coverage.",
            "Similarity search is approximate; one mixed-label group remains unresolved.",
            "Validation scores are development results, not final test or deployment evidence.",
        ],
    }

    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=output.parent) as temporary:
        staged = Path(temporary) / "baseline_v1"
        staged.mkdir()
        joblib.dump(model, staged / "model.joblib", compress=3)
        (staged / "validation_report.json").write_text(
            json.dumps(report, indent=2) + "\n", encoding="utf-8"
        )
        staged.rename(output)

    print("\nVocabulary features:", report["features"])
    print(f"Majority baseline accuracy: {dummy_results['accuracy']:.4f}")
    print(f"Model accuracy: {results['accuracy']:.4f}")
    print(f"Balanced accuracy: {results['balanced_accuracy']:.4f}")
    print(f"Macro F1: {results['macro_f1']:.4f}")
    print("\nValidation classification report:")
    print(classification_report(
        validation_labels, predictions, labels=[0, 1],
        target_names=NAMES, digits=4, zero_division=0,
    ))
    print("Confusion matrix: rows = actual, columns = predicted; label order = [0, 1]")
    print(results["confusion_matrix"])
    print("\nTest set remains unused.")
    print("Saved to:", output)


if __name__ == "__main__":
    train_baseline(Path(__file__).resolve().parent.parent)