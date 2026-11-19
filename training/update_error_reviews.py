import json
import os
import tempfile
from collections import Counter
from pathlib import Path


UPDATES = {
    ("CEAS_08.csv", 8975): (
        "legitimate",
        "Plausible news alert containing a coherent headline and article summary, "
        "with a claimed subscription and preference-management footer. No apparent "
        "credential, payment or fraudulent transfer request. Sender identity, "
        "recipient consent and link destinations are unverified. Provisional "
        "content assessment, not a verified correction to the original label.",
    ),
    ("CEAS_08.csv", 6139): (
        "legitimate",
        "Plausible news alert about Iraq's oil revenue and budget surplus. "
        "Financial figures occur in a news context rather than an investment "
        "solicitation. No apparent phishing or fraud request. Sender identity, "
        "recipient consent and link destinations are unverified. Provisional "
        "content assessment, not a verified correction to the original label.",
    ),
    ("SpamAssasin.csv", 4008): (
        "uncertain",
        "Commercial investment-newsletter promotion claiming a prior report "
        "request and offering a subscription with a refund guarantee. The text "
        "cannot establish consent to this marketing. No clear credential-theft "
        "or fraudulent transfer mechanism is visible. Sender identity, offer "
        "terms and link safety are unverified; different ordering and unsubscribe "
        "domains alone do not establish fraud. Provisional content assessment.",
    ),
    ("Ling.csv", 1970): (
        "uncertain",
        "Science-fiction convention promotion presented as a personal forwarded "
        "recommendation, with a claimed charitable purpose. It could be wanted "
        "correspondence or unsolicited promotion; recipient context and consent "
        "are unavailable. No explicit phishing or fraud mechanism is visible. "
        "The event, charity claim, sender and destination are unverified. "
        "Provisional content assessment; the original spam label is not disproved.",
    ),
    ("SpamAssasin.csv", 5462): (
        "uncertain",
        "Industry-news-style message promoting an article on industrial Linux, "
        "with vendor branding and unsubscribe instructions. Subscription status "
        "is unknown, so wanted news versus unsolicited marketing is unresolved. "
        "Unexplained trailing characters are suspicious but do not establish "
        "fraud. No explicit credential or payment request is visible. Sender "
        "identity and destinations are unverified. Provisional content assessment.",
    ),
    ("Ling.csv", 1346): (
        "ordinary_spam",
        "Apparent book-catalogue advertisement explicitly introduced as junk "
        "mail in the subject. The text supports a provisional ordinary-spam "
        "assessment. Asking for a mailing address to send a requested catalogue "
        "is not by itself evidence of phishing; no clear fraud mechanism is "
        "visible. Consent, sender identity and destination safety are unverified.",
    ),
}

CATEGORIES = {"legitimate", "ordinary_spam", "phishing_or_fraud", "uncertain"}


def update_reviews(path):
    original_bytes = path.read_bytes()
    records = json.loads(original_bytes)
    if not isinstance(records, list) or len(records) != len(UPDATES):
        raise ValueError("Expected the six-record error-review sample. Nothing saved.")

    keys = [(row["source"], row["record_number"]) for row in records]
    if len(set(keys)) != len(keys) or set(keys) != set(UPDATES):
        raise ValueError("Review records are missing, unexpected or duplicated. Nothing saved.")

    changed = 0
    preserved = 0
    for record, key in zip(records, keys):
        category = record.get("reviewed_category")
        notes = record.get("review_notes", "")
        if not isinstance(notes, str):
            raise ValueError(f"Invalid review notes for {key}. Nothing saved.")
        if category is not None:
            if category not in CATEGORIES or not notes.strip():
                raise ValueError(f"Incomplete or invalid existing review for {key}. Nothing saved.")
            preserved += 1
            continue
        if notes.strip():
            raise ValueError(f"Notes exist without a category for {key}. Nothing saved.")
        record["reviewed_category"], record["review_notes"] = UPDATES[key]
        changed += 1

    backup = path.with_name("review_sample.before_reviews.json")
    if changed:
        if not backup.exists():
            with backup.open("xb") as file:
                file.write(original_bytes)
        temporary_path = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w", encoding="utf-8", dir=path.parent,
                prefix="review_sample_", suffix=".tmp", delete=False,
            ) as file:
                temporary_path = Path(file.name)
                json.dump(records, file, ensure_ascii=False, indent=2)
                file.write("\n")
            if path.read_bytes() != original_bytes:
                raise RuntimeError("Review file changed during processing. Nothing replaced.")
            os.replace(temporary_path, path)
        finally:
            if temporary_path is not None and temporary_path.exists():
                temporary_path.unlink()

    counts = Counter(record["reviewed_category"] for record in records)
    print("New reviews saved:", changed)
    print("Existing reviews preserved:", preserved)
    print("Total records preserved:", len(records))
    for category in sorted(CATEGORIES):
        print(f"{category}: {counts[category]}")
    print("Review file:", path)
    if backup.exists():
        print("Backup:", backup)
    print("Only the sample's review fields were updated.")
    print("Dataset labels, model, validation metrics and test set are unchanged.")


if __name__ == "__main__":
    root = Path(__file__).resolve().parent.parent
    update_reviews(
        root / "data" / "private" / "baseline_v1_error_review" / "review_sample.json"
    )