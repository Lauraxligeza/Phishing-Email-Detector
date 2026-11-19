import argparse
import hashlib
import json
import sys
from importlib.metadata import version
from pathlib import Path

import joblib


MAX_BYTES = 1_000_000


def read_text(path):
    if path is not None:
        with path.open("rb") as file:
            data = file.read(MAX_BYTES + 1)
        if len(data) > MAX_BYTES:
            raise ValueError("Email file exceeds the 1 MB input limit.")
        return data.decode("utf-8-sig")

    subject = input("Subject: ").strip()
    print("Paste the plain-text body, then press Enter and Ctrl+D:", flush=True)
    body = sys.stdin.read(MAX_BYTES + 1)
    if not body.strip():
        raise ValueError("The email body is empty.")
    return subject + "\n\n" + body


def check_email(text, root):
    if not text.strip():
        raise ValueError("Email text is empty.")
    if len(text.encode("utf-8")) > MAX_BYTES:
        raise ValueError("Email text exceeds the 1 MB input limit.")

    directory = root / "models" / "baseline_v1"
    validation = json.loads(
        (directory / "validation_report.json").read_text(encoding="utf-8")
    )
    if version("scikit-learn") != validation["versions"]["scikit-learn"]:
        raise ValueError("Use the same scikit-learn version used for training.")

    benchmark = json.loads(
        (directory / "test_evaluation" / "test_report.json").read_text(
            encoding="utf-8"
        )
    )
    model_path = directory / "model.joblib"
    hasher = hashlib.sha256()
    with model_path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            hasher.update(chunk)
    if hasher.hexdigest() != benchmark["model_sha256"]:
        raise ValueError("The saved model differs from the evaluated baseline.")

    model = joblib.load(model_path)
    features = model.named_steps["tfidf"].transform([text])
    if features.nnz == 0:
        raise ValueError(
            "No learned text features matched. Unable to assess this email."
        )

    classifier = model.named_steps["classifier"]
    label = int(classifier.predict(features)[0])
    positive_column = list(classifier.classes_).index(1)
    score = float(classifier.predict_proba(features)[0, positive_column])
    return label, score


def main():
    parser = argparse.ArgumentParser(
        description="Check plain-text email with the saved binary baseline."
    )
    parser.add_argument(
        "--file",
        type=Path,
        help="UTF-8 text file: subject, blank line, then body.",
    )
    args = parser.parse_args()
    root = Path(__file__).resolve().parent

    try:
        text = read_text(args.file)
        label, score = check_email(text, root)
    except (OSError, ValueError, EOFError) as error:
        print(f"Could not check email: {error}", file=sys.stderr)
        return 1

    prediction = "spam/fraud-like" if label == 1 else "non-spam-like"
    print(f"\nPrediction: {prediction}")
    print(f"Spam/fraud model score: {score:.4f} (0 to 1)")
    print("This score is uncalibrated and is not a verified phishing probability.")
    print("The model cannot separate ordinary spam from phishing or confirm safety.")
    print("Only supplied text was analysed; links and attachments were not inspected.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())