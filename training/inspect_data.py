import csv
from collections import Counter
from pathlib import Path

csv.field_size_limit(10 * 1024 * 1024)

project_root = Path(__file__).resolve().parent.parent
data_directory = project_root / "data" / "private" / "kaggle"

for file_path in sorted(data_directory.glob("*.csv")):
    if file_path.name == "phishing_email.csv":
        continue

    with file_path.open(encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        columns = reader.fieldnames
        rows = list(reader)

    print(f"\n--- {file_path.name} ---")
    print("Rows:", len(rows))
    print("Columns:", columns)

    label_counts = Counter(row["label"] for row in rows)
    print("Label counts:", label_counts)

    print("\nMissing or blank values:")

    for column in columns or []:
        missing = 0

        for row in rows:
            value = row[column]

            if value is None or value.strip() == "":
                missing += 1

        print(f"{column}: {missing}")

    text_counts = Counter()
    labels_by_text = {}
    empty_text_rows = 0

    for row in rows:
        subject = row["subject"] or ""
        body = row["body"] or ""
        text_key = (subject, body)

        if not subject.strip() and not body.strip():
            empty_text_rows += 1
            continue

        text_counts[text_key] += 1

        if text_key not in labels_by_text:
            labels_by_text[text_key] = set()

        labels_by_text[text_key].add(row["label"])

    duplicate_rows = sum(
        count - 1 for count in text_counts.values()
    )

    conflicting_groups = sum(
        len(labels) > 1 for labels in labels_by_text.values()
    )

    print("\nText checks:")
    print("Rows with neither subject nor body:", empty_text_rows)
    print("Extra exact duplicate rows:", duplicate_rows)
    print("Text groups with conflicting labels:", conflicting_groups)