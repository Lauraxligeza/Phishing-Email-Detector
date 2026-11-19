import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path

import joblib
import sklearn
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    root = parser.parse_args().root
    source = root / "data/private/category_review_batch_01/batch_01_pilot.jsonl"
    output = root / "models/category_pilot_v1"
    raw = source.read_bytes()
    rows = [json.loads(line) for line in raw.splitlines()]
    labels = [row["pilot_label"] for row in rows]
    texts = [row["text"] for row in rows]
    if len(rows) != 60 or len({row["review_id"] for row in rows}) != 60:
        raise ValueError("Expected 60 distinct review records.")
    if set(labels) != {"legitimate", "ordinary_spam", "phishing_or_fraud"}:
        raise ValueError("Expected all three pilot categories.")
    if any(not isinstance(text, str) or not text.strip() for text in texts):
        raise ValueError("An email has missing text.")
    if output.exists():
        raise FileExistsError(f"Pilot already exists at {output}")

    model = make_pipeline(TfidfVectorizer(sublinear_tf=True),
                          LogisticRegression(solver="lbfgs", max_iter=1000))
    model.fit(texts, labels)
    output.mkdir(parents=True)
    path = output / "model.joblib"
    joblib.dump(model, path, compress=3)
    restored = joblib.load(path)
    if not (restored.predict(texts) == model.predict(texts)).all():
        raise RuntimeError("Reloaded predictions differ.")
    report = dict(training_records=len(rows), label_counts=dict(Counter(labels)),
                  sklearn_version=sklearn.__version__, independently_evaluated=False,
                  input_sha256=hashlib.sha256(raw).hexdigest())
    (output / "training_report.json").write_text(json.dumps(report, indent=2) + "\n")
    print("Training records:", len(rows))
    print("Label counts:", dict(Counter(labels)))
    print("Reload check passed. Saved to:", path)


if __name__ == "__main__":
    main()
