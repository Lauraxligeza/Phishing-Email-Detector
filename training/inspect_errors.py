import hashlib
import json
from pathlib import Path

import joblib


def export_errors(root):
    model_dir = root / "models" / "baseline_v1"
    validation_path = root / "data" / "splits" / "validation.jsonl"
    output_dir = root / "data" / "private" / "baseline_v1_error_review"

    if output_dir.exists():
        raise FileExistsError(f"{output_dir} already exists. Nothing overwritten.")

    report = json.loads((model_dir / "validation_report.json").read_text(encoding="utf-8"))
    data = validation_path.read_bytes()
    if hashlib.sha256(data).hexdigest() != report["input_sha256"]["validation.jsonl"]:
        raise ValueError("Validation data changed since training. Nothing saved.")

    rows = [json.loads(line) for line in data.splitlines()]
    model = joblib.load(model_dir / "model.joblib")
    print("Finding validation errors...", flush=True)
    predictions = model.predict([row["text"] for row in rows])
    indices = [i for i, row in enumerate(rows) if int(predictions[i]) != row["label"]]
    matrix = report["model"]["confusion_matrix"]
    if len(indices) != matrix[0][1] + matrix[1][0]:
        raise ValueError("Error count differs from the saved report. Nothing saved.")

    errors = []
    if indices:
        positive_column = list(model.classes_).index(1)
        scores = model.predict_proba([rows[i]["text"] for i in indices])[:, positive_column]
        for index, score in zip(indices, scores):
            row = rows[index]
            errors.append({
                "source": row["source"],
                "record_number": row["record_number"],
                "group_id": row["group_id"],
                "original_label": row["label"],
                "predicted_label": int(predictions[index]),
                "error_type": "false_positive" if row["label"] == 0 else "false_negative",
                "model_score_class_1": float(score),
                "text": row["text"],
                "reviewed_category": None,
                "review_notes": "",
            })

    sample = []
    used_groups = set()
    for error_type in ("false_positive", "false_negative"):
        candidates = [row for row in errors if row["error_type"] == error_type]
        candidates.sort(key=lambda row: (
            -row["model_score_class_1"] if error_type == "false_positive"
            else row["model_score_class_1"],
            row["source"], row["record_number"],
        ))
        selected = 0
        for row in candidates:
            if row["group_id"] in used_groups:
                continue
            sample.append(row)
            used_groups.add(row["group_id"])
            selected += 1
            if selected == 3:
                break

    output_dir.mkdir(parents=True)
    for name, records in (("all_errors.json", errors), ("review_sample.json", sample)):
        (output_dir / name).write_text(
            json.dumps(records, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )

    print("Validation errors exported:", len(errors))
    print("False positives:", sum(row["error_type"] == "false_positive" for row in errors))
    print("False negatives:", sum(row["error_type"] == "false_negative" for row in errors))
    print("Review samples:", len(sample))
    print("Sample selection: up to three strongest disagreements per error type, distinct groups.")
    print("Scores are uncalibrated model estimates, not verified phishing probabilities.")
    print("Original labels, splits and model remain unchanged. Test set remains unused.")
    print("Saved to:", output_dir)


if __name__ == "__main__":
    export_errors(Path(__file__).resolve().parent.parent)