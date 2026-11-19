import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path


POLICY = """# Initial data preparation policy

- Original subjects, bodies, metadata and source labels are preserved.
- Model text uses decoded subjects and available plain text, including extracted HTML text.
- Unresolved decoding, missing body text, possible truncation, uncertain sample reviews and conflicting duplicate labels exclude records from the initial baseline pool.
- Eligibility means passing these initial checks, not verified safety, correct labels, English-language content or complete extraction.
- Original label 0 is used as corpus non-spam; original label 1 as corpus spam/fraud. These are inherited binary labels, not three-class phishing labels.
- The 30 assistant-reviewed samples are development material, not independent evaluation ground truth. Their entire duplicate/campaign groups must stay out of validation and test sets.
- Both original and prepared-text duplicate identifiers are retained. Related groups must be combined before splitting; similar campaign messages still need grouping.
- No records are deleted. Excluded records remain available for investigation.
- HTML extraction covers the 52 identified HTML bodies only. CSS visibility, image text, attachments and additional unrecognized encodings are not resolved.
- Selecting a MIME body can omit alternatives, footers or preambles; warnings remain attached. Inferred MIME structures are not observed original headers.
- Commercial-use clearance and source-license verification remain unresolved.
- This completes initial preparation, not training, final labels or production validation.
"""


def prepare_record(record):
    flags = []
    subject = record["subject_decoded"]
    body = record["body_text_candidate"]

    if record["subject_decode_status"] == "needs_review":
        flags.append("subject_decode_unresolved")

    if record["body_decode_status"] == "needs_review":
        flags.append("body_decode_unresolved")
        body = None

    if record["body_decode_status"] == "html_ready":
        if record["html_text_status"] == "extracted":
            body = record["html_text_candidate"]
        else:
            body = None
            flags.append("html_text_unavailable")

    if body is None or not body.strip():
        flags.append("empty_or_unavailable_body")

    if any(
        "closing boundary missing" in warning.lower()
        for warning in record["body_decode_warnings"]
    ):
        flags.append("possible_truncation")

    category = record.get("reviewed_category")

    if category == "uncertain":
        flags.append("review_uncertain")

    label = record["original_label"]

    if label not in {"0", "1"}:
        raise ValueError("Unexpected original label.")

    text_group = None
    model_text = None

    if body is not None and body.strip():
        model_text = subject + "\n\n" + body

        normalized_pair = [
            " ".join(subject.split()),
            " ".join(body.split()),
        ]

        serialized = json.dumps(
            normalized_pair,
            ensure_ascii=False,
            separators=(",", ":"),
        )

        text_group = hashlib.sha256(
            serialized.encode("utf-8")
        ).hexdigest()

    record["model_text_candidate"] = model_text
    record["prepared_text_group"] = text_group
    record["baseline_label"] = int(label)
    record["preparation_flags"] = flags

    record["split_constraint"] = (
        "development_only"
        if category is not None
        else "unassigned"
    )

    return record


def main():
    root = Path(__file__).resolve().parent.parent
    directory = root / "data" / "processed"

    input_path = directory / "emails_text_extracted.jsonl"
    staged_path = directory / "emails_prepared.stage.jsonl"
    output_path = directory / "emails_prepared.jsonl"
    temporary_path = output_path.with_suffix(".tmp")

    group_labels = defaultdict(set)

    print(
        "Consolidating text and preparation flags...",
        flush=True,
    )

    with (
        input_path.open(encoding="utf-8") as source,
        staged_path.open("w", encoding="utf-8") as target,
    ):
        for line in source:
            record = prepare_record(json.loads(line))

            for field in (
                "duplicate_group",
                "prepared_text_group",
            ):
                if record[field] is not None:
                    group_labels[
                        (field, record[field])
                    ].add(record["baseline_label"])

            target.write(
                json.dumps(record, ensure_ascii=False) + "\n"
            )

    totals = Counter()
    exclusions = Counter()
    eligible_labels = Counter()

    with (
        staged_path.open(encoding="utf-8") as source,
        temporary_path.open("w", encoding="utf-8") as target,
    ):
        for line in source:
            record = json.loads(line)

            if any(
                record[field] is not None
                and len(
                    group_labels[(field, record[field])]
                ) > 1
                for field in (
                    "duplicate_group",
                    "prepared_text_group",
                )
            ):
                record["preparation_flags"].append(
                    "conflicting_duplicate_labels"
                )

            eligible = not record["preparation_flags"]
            record["baseline_eligible"] = eligible

            totals["records"] += 1
            totals[
                "eligible" if eligible else "excluded"
            ] += 1

            exclusions.update(record["preparation_flags"])

            if record["split_constraint"] == "development_only":
                totals["development_only"] += 1

            if eligible:
                eligible_labels[
                    str(record["baseline_label"])
                ] += 1

            target.write(
                json.dumps(record, ensure_ascii=False) + "\n"
            )

    temporary_path.replace(output_path)
    staged_path.unlink()

    report = {
        "totals": dict(totals),
        "exclusion_reasons_overlapping": dict(exclusions),
        "eligible_original_labels": dict(eligible_labels),
        "note": (
            "Counts are records, not independent examples; "
            "duplicates remain."
        ),
    }

    (directory / "preparation_report.json").write_text(
        json.dumps(report, indent=2) + "\n",
        encoding="utf-8",
    )

    docs = root / "docs"
    docs.mkdir(exist_ok=True)

    (docs / "data_preparation_generated.md").write_text(
        POLICY,
        encoding="utf-8",
    )

    print("Records preserved:", totals["records"])
    print("Eligible for initial baseline:", totals["eligible"])
    print("Excluded from initial baseline:", totals["excluded"])
    print(
        "Development-only reviewed records:",
        totals["development_only"],
    )

    print("\nExclusion reasons (can overlap):")

    for reason, count in exclusions.most_common():
        print(f"{reason}: {count}")

    print(
        "\nEligible original-label counts:",
        dict(eligible_labels),
    )
    print("Saved to:", output_path)


if __name__ == "__main__":
    main()