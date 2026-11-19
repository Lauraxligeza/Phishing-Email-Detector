import csv
from collections import Counter
from itertools import combinations
from pathlib import Path

csv.field_size_limit(10 * 1024 * 1024)

project_root = Path(__file__).resolve().parent.parent
data_directory = project_root / "data" / "private" / "kaggle"

text_groups = {}
total_rows = 0
empty_text_rows = 0

for file_path in sorted(data_directory.glob("*.csv")):
    if file_path.name == "phishing_email.csv":
        continue

    with file_path.open(encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)

        for row in reader:
            total_rows += 1

            subject = row["subject"] or ""
            body = row["body"] or ""

            if not subject.strip() and not body.strip():
                empty_text_rows += 1
                continue

            text_key = (subject, body)

            if text_key not in text_groups:
                text_groups[text_key] = {
                    "count": 0,
                    "sources": set(),
                    "labels": set(),
                }

            group = text_groups[text_key]
            group["count"] += 1
            group["sources"].add(file_path.name)
            group["labels"].add(row["label"])

duplicate_rows = sum(
    group["count"] - 1 for group in text_groups.values()
)

cross_source_groups = 0
conflicting_groups = 0
source_pairs = Counter()

for group in text_groups.values():
    if len(group["labels"]) > 1:
        conflicting_groups += 1

    if len(group["sources"]) > 1:
        cross_source_groups += 1

        for pair in combinations(sorted(group["sources"]), 2):
            source_pairs[pair] += 1

print("Total rows:", total_rows)
print("Rows with neither subject nor body:", empty_text_rows)
print("Unique nonblank subject/body pairs:", len(text_groups))
print("Extra exact duplicate rows:", duplicate_rows)
print("Text groups appearing in multiple sources:", cross_source_groups)
print("Text groups with conflicting original labels:", conflicting_groups)

print("\nShared text groups by source pair:")

if not source_pairs:
    print("None found.")
else:
    for (first, second), count in sorted(source_pairs.items()):
        print(f"{first} <-> {second}: {count}")