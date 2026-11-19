import csv
import json
import random
from collections import defaultdict
from pathlib import Path

csv.field_size_limit(10 * 1024 * 1024)

project_root = Path(__file__).resolve().parent.parent
data_directory = project_root / "data" / "private" / "kaggle"
output_path = project_root / "data" / "private" / "review_samples.json"

rng = random.Random(42)
samples = []

for file_path in sorted(data_directory.glob("*.csv")):
    if file_path.name == "phishing_email.csv":
        continue

    records_by_label = defaultdict(list)
    seen = set()

    with file_path.open(encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)

        for record_number, row in enumerate(reader, start=1):
            subject = row["subject"] or ""
            body = row["body"] or ""

            text_key = (
                " ".join(subject.split()),
                " ".join(body.split()),
            )

            if not any(text_key) or text_key in seen:
                continue

            seen.add(text_key)

            records_by_label[row["label"]].append({
                "source": file_path.name,
                "record_number": record_number,
                "original_label": row["label"],
                "subject": subject,
                "body": body,
                "reviewed_category": None,
                "review_notes": "",
            })

    for label in sorted(records_by_label):
        candidates = records_by_label[label]
        samples.extend(rng.sample(candidates, min(3, len(candidates))))

with output_path.open("x", encoding="utf-8") as file:
    json.dump(samples, file, ensure_ascii=False, indent=2)

print("Samples selected:", len(samples))
print("Saved to:", output_path)