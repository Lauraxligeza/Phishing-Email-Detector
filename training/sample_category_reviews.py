import hashlib
import json
import tempfile
from collections import Counter, defaultdict
from pathlib import Path


SEED = "category-review-pilot-v1"
QUOTAS = {
    "CEAS_08.csv": {0: 5, 1: 5},
    "Enron.csv": {0: 5, 1: 5},
    "Ling.csv": {0: 5, 1: 5},
    "Nazario.csv": {1: 10},
    "Nigerian_Fraud.csv": {1: 10},
    "SpamAssasin.csv": {0: 5, 1: 5},
}


def digest(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def rank(row):
    return digest(json.dumps([SEED, row["source"], row["record_number"]]))


def write_json(path, value):
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def sample_reviews(root):
    splits = root / "data" / "splits"
    private = root / "data" / "private"
    output = private / "category_review_batch_01"
    if output.exists():
        raise FileExistsError(
            f"{output} already exists. Existing reviews are preserved."
        )

    previous = json.loads(
        (private / "review_samples.json").read_text(encoding="utf-8")
    )
    reviewed_keys = {
        (row["source"], row["record_number"])
        for row in previous
        if row.get("reviewed_category") is not None
    }
    reviewed_groups = set()
    matched_reviews = set()
    training_entries = {}
    group_splits = {}

    print("Checking split membership and previous reviews...", flush=True)

    with (splits / "manifest.jsonl").open(encoding="utf-8") as file:
        for line in file:
            entry = json.loads(line)
            key = (entry["source"], entry["record_number"])
            group = entry["group_id"]
            assignment = entry["group_split"]

            if group in group_splits and group_splits[group] != assignment:
                raise ValueError(
                    "A group has multiple split assignments. Nothing saved."
                )

            group_splits[group] = assignment

            if key in reviewed_keys:
                reviewed_groups.add(group)
                matched_reviews.add(key)

            if entry["status"] == "selected" and entry["split"] == "train":
                if key in training_entries or assignment != "train":
                    raise ValueError("Invalid training manifest. Nothing saved.")
                training_entries[key] = group

    if matched_reviews != reviewed_keys:
        raise ValueError(
            "Some previous reviews are missing from the manifest. Nothing saved."
        )

    buckets = defaultdict(list)
    seen = set()

    with (splits / "train.jsonl").open(encoding="utf-8") as file:
        for line in file:
            row = json.loads(line)
            key = (row["source"], row["record_number"])

            if key in seen or training_entries.get(key) != row["group_id"]:
                raise ValueError(
                    "Training records disagree with the manifest. Nothing saved."
                )

            seen.add(key)

            if type(row["label"]) is not int or row["label"] not in (0, 1):
                raise ValueError("Unexpected training label. Nothing saved.")

            if not isinstance(row["text"], str) or not row["text"].strip():
                raise ValueError("Missing training text. Nothing saved.")

            if row["group_id"] not in reviewed_groups:
                buckets[(row["source"], row["label"])].append(row)

    if seen != set(training_entries):
        raise ValueError("Training records are missing. Nothing saved.")

    selected = []
    used_groups = set()

    for source, labels in QUOTAS.items():
        for label, required in labels.items():
            added = 0

            for row in sorted(buckets[(source, label)], key=rank):
                if row["group_id"] in used_groups:
                    continue

                selected.append(row)
                used_groups.add(row["group_id"])
                added += 1

                if added == required:
                    break

            if added != required:
                raise ValueError(
                    f"Too few available groups for {source}, label {label}. "
                    "Nothing saved."
                )

    selected.sort(key=lambda row: digest("review-order:" + rank(row)))
    reviews = []
    provenance = []

    for number, row in enumerate(selected, 1):
        review_id = f"B01-{number:03d}"

        reviews.append({
            "review_id": review_id,
            "text": row["text"],
            "reviewed_category": None,
            "review_notes": "",
        })

        provenance.append({
            "review_id": review_id,
            "source": row["source"],
            "record_number": row["record_number"],
            "group_id": row["group_id"],
            "original_label": row["label"],
            "text_sha256": digest(row["text"]),
        })

    report = {
        "seed": SEED,
        "records": len(reviews),
        "split": "train",
        "previously_reviewed_groups_excluded": len(reviewed_groups),
        "distinct_selected_groups": len(used_groups),
        "source_counts": dict(Counter(row["source"] for row in selected)),
        "original_label_counts": dict(
            Counter(row["label"] for row in selected)
        ),
        "note": (
            "Training-only labelling pilot, not an evaluation set "
            "or representative prevalence sample."
        ),
        "review_method": (
            "Unassigned; content assessments require review and adjudication."
        ),
    }

    with tempfile.TemporaryDirectory(dir=private) as temporary:
        staged = Path(temporary) / "batch"
        staged.mkdir()
        write_json(staged / "review_samples.json", reviews)
        write_json(staged / "provenance.json", provenance)
        write_json(staged / "sampling_report.json", report)
        staged.rename(output)

    print("Review records saved:", len(reviews))
    print("Distinct training groups:", len(used_groups))
    print("Previously reviewed groups excluded:", len(reviewed_groups))

    for source, count in report["source_counts"].items():
        print(f"{source}: {count}")

    print("Original labels are preserved separately in provenance.json.")
    print("No model predictions were added to the review sample.")
    print("Saved to:", output / "review_samples.json")


if __name__ == "__main__":
    sample_reviews(Path(__file__).resolve().parent.parent)