import json
import platform
import tempfile
from collections import Counter
from datetime import datetime, timezone
from importlib.metadata import version
from itertools import combinations
from pathlib import Path

import joblib
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix

from train_baseline import NAMES, file_hash, metrics, read_split


def evaluate_test(root):
    splits = root / "data" / "splits"
    model_dir = root / "models" / "baseline_v1"
    output = model_dir / "test_evaluation"
    if output.exists():
        raise FileExistsError(f"Evaluation already exists: {output}. Nothing overwritten.")

    validation_path = model_dir / "validation_report.json"
    validation_report = json.loads(validation_path.read_text(encoding="utf-8"))
    if version("scikit-learn") != validation_report["versions"]["scikit-learn"]:
        raise ValueError("Use the same scikit-learn version used for training.")
    for name, expected_hash in validation_report["input_sha256"].items():
        if file_hash(splits / name) != expected_hash:
            raise ValueError(f"{name} changed since training. Evaluation stopped.")

    print("Checking split identities, groups and label counts...", flush=True)
    split_report = json.loads((splits / "split_report.json").read_text(encoding="utf-8"))
    identities = {}
    groups = {}
    label_counts = {}
    test_rows = None
    for name in ("train", "validation", "test"):
        rows = read_split(splits / f"{name}.jsonl")
        identities[name] = {(row["source"], row["record_number"]) for row in rows}
        groups[name] = {row["group_id"] for row in rows}
        label_counts[name] = Counter(row["label"] for row in rows)
        actual = {str(label): count for label, count in label_counts[name].items()}
        if actual != split_report["split_label_counts"][name]:
            raise ValueError(f"{name} label counts differ from the split report.")
        if name == "test":
            test_rows = rows
    del rows
    for left, right in combinations(identities, 2):
        if identities[left] & identities[right] or groups[left] & groups[right]:
            raise ValueError(f"Record or group overlap between {left} and {right}.")

    model_path = model_dir / "model.joblib"
    model_hash = file_hash(model_path)
    model = joblib.load(model_path)
    for step, expected in validation_report["settings"].items():
        parameters = model.named_steps[step].get_params()
        actual = {key: parameters[key] for key in expected}
        if json.dumps(actual, sort_keys=True) != json.dumps(expected, sort_keys=True):
            raise ValueError(f"Saved {step} settings differ from the validation report.")

    print("Evaluating the saved baseline on", len(test_rows), "test records...", flush=True)
    labels = [row["label"] for row in test_rows]
    predictions = model.predict([row["text"] for row in test_rows])
    results = metrics(labels, predictions)
    majority_label = max((0, 1), key=lambda label: label_counts["train"][label])
    majority_results = metrics(labels, [majority_label] * len(labels))

    by_source = {}
    for source in sorted({row["source"] for row in test_rows}):
        indices = [i for i, row in enumerate(test_rows) if row["source"] == source]
        source_labels = [labels[i] for i in indices]
        source_predictions = [int(predictions[i]) for i in indices]
        by_source[source] = {
            "records": len(indices), "label_counts": dict(Counter(source_labels)),
            "accuracy": accuracy_score(source_labels, source_predictions),
            "confusion_matrix": confusion_matrix(
                source_labels, source_predictions, labels=[0, 1]
            ).tolist(),
        }

    report = {
        "evaluated_at_utc": datetime.now(timezone.utc).isoformat(),
        "evaluation_split": "test", "test_records": len(test_rows),
        "label_names": dict(enumerate(NAMES)),
        "model_sha256": model_hash,
        "validation_report_sha256": file_hash(validation_path),
        "input_sha256": {name: file_hash(splits / name) for name in (
            "train.jsonl", "validation.jsonl", "test.jsonl", "split_report.json",
        )},
        "script_sha256": file_hash(Path(__file__)),
        "helper_script_sha256": file_hash(Path(__file__).with_name("train_baseline.py")),
        "versions": {"python": platform.python_version(), **{
            name: version(name) for name in ("scikit-learn", "numpy", "scipy", "joblib")
        }},
        "settings": validation_report["settings"],
        "decision_rule": "Saved pipeline.predict; no refitting or threshold tuning.",
        "model": results, "majority_baseline": majority_results,
        "test_by_source": by_source,
        "limitations": [
            "This is an internal corpus benchmark using inherited binary labels.",
            "It does not measure separate phishing detection or performance on new inboxes.",
            "Short and long texts were restricted to training; test coverage is narrower.",
            "Similarity grouping is approximate; one mixed-label group remains unresolved.",
            "Do not use these test results to choose settings and then claim a fresh test.",
        ],
    }

    if file_hash(model_path) != model_hash:
        raise RuntimeError("Saved model changed during evaluation. Nothing published.")
    with tempfile.TemporaryDirectory(dir=model_dir) as temporary:
        staged = Path(temporary) / "test_evaluation"
        staged.mkdir()
        (staged / "test_report.json").write_text(
            json.dumps(report, indent=2) + "\n", encoding="utf-8"
        )
        staged.rename(output)

    print(f"\nMajority baseline accuracy: {majority_results['accuracy']:.4f}")
    print(f"Test accuracy: {results['accuracy']:.4f}")
    print(f"Balanced accuracy: {results['balanced_accuracy']:.4f}")
    print(f"Macro F1: {results['macro_f1']:.4f}")
    print("\nTest classification report:")
    print(classification_report(
        labels, predictions, labels=[0, 1], target_names=NAMES,
        digits=4, zero_division=0,
    ))
    print("Confusion matrix: rows = actual, columns = predicted; label order = [0, 1]")
    print(results["confusion_matrix"])
    print("\nSaved model and validation report are unchanged.")
    print("Test evaluation is now recorded. Use validation for further development.")
    print("Saved to:", output / "test_report.json")


if __name__ == "__main__":
    evaluate_test(Path(__file__).resolve().parent.parent)