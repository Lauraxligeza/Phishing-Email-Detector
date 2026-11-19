import json
import re
from collections import Counter, defaultdict
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent
input_path = (
    project_root
    / "data"
    / "processed"
    / "emails_subjects_decoded.jsonl"
)

encoding_header = re.compile(
    r"^[ \t]*Content-Transfer-Encoding:[ \t]*"
    r"([A-Za-z0-9-]+)[ \t]*\r?$",
    re.IGNORECASE | re.MULTILINE,
)

counts = Counter()
examples = defaultdict(list)
total_records = 0
records_with_headers = 0

print("Inspecting email bodies...", flush=True)

with input_path.open(encoding="utf-8") as file:
    for line in file:
        record = json.loads(line)
        total_records += 1

        body = record["body"]
        matches = list(encoding_header.finditer(body))

        if not matches:
            continue

        records_with_headers += 1
        seen_encodings = set()

        for match in matches:
            encoding = match.group(1).lower()

            if encoding in seen_encodings:
                continue

            seen_encodings.add(encoding)
            counts[encoding] += 1

            if len(examples[encoding]) < 2:
                start = max(0, match.start() - 250)
                end = min(len(body), match.end() + 200)

                examples[encoding].append({
                    "source": record["source"],
                    "record_number": record["record_number"],
                    "context": body[start:end],
                })

print("Records inspected:", total_records)
print("Records with candidate encoding headers:", records_with_headers)

for encoding, count in sorted(counts.items()):
    print(f"\n{encoding}: {count} records")

    for example in examples[encoding]:
        print(
            f"  {example['source']}, "
            f"record {example['record_number']}"
        )
        print("  Context:", repr(example["context"]))