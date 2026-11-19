import csv
import hashlib
import json
from collections import Counter
from pathlib import Path

csv.field_size_limit(10 * 1024 * 1024)

project_root = Path(__file__).resolve().parent.parent
input_directory = project_root / "data" / "private" / "kaggle"
review_path = project_root / "data" / "private" / "review_samples.json"
output_directory = project_root / "data" / "processed"

source_files = [
    "CEAS_08.csv",
    "Enron.csv",
    "Ling.csv",
    "Nazario.csv",
    "Nigerian_Fraud.csv",
    "SpamAssasin.csv",
]

reviews = json.loads(review_path.read_text(encoding="utf-8"))
reviews_by_id = {}

for review in reviews:
    key = (review["source"], review["record_number"])

    if key in reviews_by_id:
        raise ValueError(f"Duplicate review identifier: {key}")

    reviews_by_id[key] = review

output_directory.mkdir(parents=True, exist_ok=True)
output_path = output_directory / "emails.jsonl"
temporary_path = output_directory / "emails.jsonl.tmp"

group_counts = Counter()
source_counts = Counter()
matched_reviews = set()
reviewed_count = 0

with temporary_path.open("w", encoding="utf-8") as output_file:
    for filename in source_files:
        file_path = input_directory / filename

        with file_path.open(encoding="utf-8-sig", newline="") as input_file:
            reader = csv.DictReader(input_file)

            for record_number, row in enumerate(reader, start=1):
                subject = row["subject"] or ""
                body = row["body"] or ""
                original_label = row["label"]

                if original_label not in {"0", "1"}:
                    raise ValueError(
                        f"Unexpected label in {filename}, record {record_number}"
                    )

                normalized_pair = [
                    " ".join(subject.split()),
                    " ".join(body.split()),
                ]

                if not any(normalized_pair):
                    raise ValueError(
                        f"Empty text in {filename}, record {record_number}"
                    )

                fingerprint_input = json.dumps(
                    normalized_pair,
                    ensure_ascii=False,
                    separators=(",", ":"),
                )

                group_id = hashlib.sha256(
                    fingerprint_input.encode("utf-8")
                ).hexdigest()

                key = (filename, record_number)
                review = reviews_by_id.get(key)

                if review is not None:
                    if (
                        review["subject"] != subject
                        or review["body"] != body
                        or review["original_label"] != original_label
                    ):
                        raise ValueError(f"Review does not match source: {key}")

                    matched_reviews.add(key)

                category = (
                    review.get("reviewed_category") if review else None
                )

                record = {
                    "source": filename,
                    "record_number": record_number,
                    "original_label": original_label,
                    "subject": subject,
                    "body": body,
                    "duplicate_group": group_id,
                    "reviewed_category": category,
                    "review_notes": review.get("review_notes", "") if review else "",
                    "review_method": (
                        "assistant_content_review" if category else None
                    ),
                    "metadata": {
                        name: value
                        for name, value in row.items()
                        if name not in {"subject", "body", "label"}
                    },
                }

                output_file.write(
                    json.dumps(record, ensure_ascii=False) + "\n"
                )

                group_counts[group_id] += 1
                source_counts[filename] += 1

                if category is not None:
                    reviewed_count += 1

    unmatched = set(reviews_by_id) - matched_reviews

    if unmatched:
        raise ValueError(f"Reviews missing from source files: {sorted(unmatched)}")

temporary_path.replace(output_path)

print("Records saved:", sum(source_counts.values()))
print("Distinct normalized text groups:", len(group_counts))
print("Extra copies:", sum(count - 1 for count in group_counts.values()))
print("Reviewed records attached:", reviewed_count)
print("Saved to:", output_path)