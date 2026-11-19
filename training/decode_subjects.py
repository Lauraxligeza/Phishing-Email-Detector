import json
import re
from collections import Counter
from email.errors import HeaderParseError
from email.header import decode_header
from pathlib import Path


encoded_word = re.compile(
    r"=\?[^?\s]+\?[bBqQ]\?[^?\s]*\?="
)

encoded_start = re.compile(
    r"=\?[^?\s]+\?[bBqQ]\?"
)


def decode_subject(subject):
    parts = []
    position = 0
    previous_encoded = False
    found = False

    try:
        for match in encoded_word.finditer(subject):
            gap = subject[position:match.start()]

            if encoded_start.search(gap):
                return subject, "needs_review", [
                    "Incomplete or malformed encoded word."
                ]

            if not (previous_encoded and gap.isspace()):
                parts.append(gap)

            for value, charset in decode_header(match.group()):
                if isinstance(value, bytes):
                    parts.append(
                        value.decode(charset or "ascii", errors="strict")
                    )
                else:
                    parts.append(value)

            position = match.end()
            previous_encoded = True
            found = True

        remainder = subject[position:]

        if encoded_start.search(remainder):
            return subject, "needs_review", [
                "Incomplete or malformed encoded word."
            ]

        parts.append(remainder)

        if not found:
            return subject, "unchanged", []

        return "".join(parts), "decoded", []

    except (LookupError, UnicodeError, HeaderParseError, ValueError) as error:
        return subject, "needs_review", [
            f"Subject decoding failed: {type(error).__name__}"
        ]


def main():
    project_root = Path(__file__).resolve().parent.parent
    data_directory = project_root / "data" / "processed"

    input_path = data_directory / "emails.jsonl"
    output_path = data_directory / "emails_subjects_decoded.jsonl"
    temporary_path = output_path.with_suffix(".tmp")

    counts = Counter()
    examples = []

    with (
        input_path.open(encoding="utf-8") as input_file,
        temporary_path.open("w", encoding="utf-8") as output_file,
    ):
        for line in input_file:
            record = json.loads(line)

            decoded, status, warnings = decode_subject(record["subject"])

            record["subject_decoded"] = decoded
            record["subject_decode_status"] = status
            record["subject_decode_warnings"] = warnings

            output_file.write(
                json.dumps(record, ensure_ascii=False) + "\n"
            )

            counts[status] += 1

            if status == "needs_review" and len(examples) < 5:
                examples.append(
                    (
                        record["source"],
                        record["record_number"],
                        warnings,
                    )
                )

    temporary_path.replace(output_path)

    print("Records processed:", sum(counts.values()))
    print("Subjects decoded:", counts["decoded"])
    print("Subjects unchanged:", counts["unchanged"])
    print("Subjects needing review:", counts["needs_review"])
    print("Saved to:", output_path)

    if examples:
        print("\nFirst subject-decoding warnings:")

        for source, record_number, warnings in examples:
            print(f"{source}, record {record_number}: {warnings}")


if __name__ == "__main__":
    main()