import csv
from collections import defaultdict
from pathlib import Path

csv.field_size_limit(10 * 1024 * 1024)

project_root = Path(__file__).resolve().parent.parent
data_directory = project_root / "data" / "private" / "kaggle"

groups = defaultdict(list)

for file_path in sorted(data_directory.glob("*.csv")):
    if file_path.name == "phishing_email.csv":
        continue

    with file_path.open(encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)

        for record_number, row in enumerate(reader, start=1):
            subject = " ".join((row["subject"] or "").split())
            body = " ".join((row["body"] or "").split())

            if not subject and not body:
                continue

            text_key = (subject, body)

            groups[text_key].append(
                (file_path.name, record_number, row["label"])
            )

duplicate_groups = [
    records for records in groups.values()
    if len(records) > 1
]

extra_copies = sum(
    len(records) - 1 for records in duplicate_groups
)

conflicting_groups = sum(
    len({label for source, record, label in records}) > 1
    for records in duplicate_groups
)

print("Whitespace-normalized duplicate groups:", len(duplicate_groups))
print("Extra copies:", extra_copies)
print("Groups with conflicting original labels:", conflicting_groups)

print("\nFirst five duplicate groups:")

for group_number, records in enumerate(duplicate_groups[:5], start=1):
    print(f"\nGroup {group_number}")

    for source, record_number, label in records:
        print(f"  {source}, record {record_number}, label {label}")

if not duplicate_groups:
    print("None found.")