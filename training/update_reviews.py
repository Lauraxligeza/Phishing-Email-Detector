import json
from collections import Counter
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent
file_path = project_root / "data" / "private" / "review_samples.json"
backup_path = file_path.with_name("review_samples.before_batch_2.json")

updates = {
    ("CEAS_08.csv", 14578): (
        "phishing_or_fraud",
        "Apparent lottery scam. A large prize claim directs the recipient "
        "to a personal Gmail address for collection procedures. "
        "Assessment is based on the supplied text.",
    ),
    ("CEAS_08.csv", 13350): (
        "uncertain",
        "Suspicious celebrity sexual-content bait. The supplied text "
        "provides no destination or sufficient detail to distinguish "
        "ordinary spam from a malicious lure.",
    ),
    ("CEAS_08.csv", 8477): (
        "ordinary_spam",
        "Apparent medicine advertisement with obfuscated words. "
        "No explicit phishing or fraud request is visible. "
        "Recipient consent and product legitimacy are unknown.",
    ),
    ("Enron.csv", 16657): (
        "legitimate",
        "Plausible workplace correspondence about a recording of "
        "transaction details. No apparent phishing or fraud request "
        "in the text. The referenced recording was not inspected.",
    ),

    ("Enron.csv", 1720): (
        "legitimate",
        "Plausible workplace message sharing upcoming discussion material. "
        "The referenced document was not inspected.",
    ),
    ("Enron.csv", 14195): (
        "legitimate",
        "Routine contact-number update without an apparent fraud request. "
        "Sender identity is unverified.",
    ),
    ("Enron.csv", 27947): (
        "uncertain",
        "An unclaimed-computer promotion asks the reader to claim a PC. "
        "Missing destinations and offer conditions prevent distinguishing "
        "ordinary promotion from prize fraud.",
    ),
    ("Enron.csv", 23304): (
        "phishing_or_fraud",
        "Apparent inheritance-transfer scam asking the recipient to "
        "impersonate a deceased depositor's relative, provide personal "
        "details, and receive a share of a large transfer.",
    ),
    ("Enron.csv", 9228): (
        "ordinary_spam",
        "Apparent bulk advertisement for discounted software. "
        "No explicit credential theft or fraudulent transfer request. "
        "Consent, software authenticity, and destination safety are unverified.",
    ),
    ("Ling.csv", 2069): (
        "legitimate",
        "Substantive discussion about language learning and grammar "
        "instruction without an apparent commercial or fraudulent request.",
    ),
    ("Ling.csv", 150): (
        "legitimate",
        "Academic debate about pronouns, gender, and linguistic markedness. "
        "Controversial views and sexual terminology do not themselves "
        "establish spam or phishing.",
    ),
    ("Ling.csv", 142): (
        "legitimate",
        "Research question about writing systems and pronunciation "
        "inviting scholarly replies. No apparent fraud request.",
    ),
    ("Ling.csv", 354): (
        "phishing_or_fraud",
        "Apparent money-chain scheme requiring cash payments, shifting "
        "recipient names, and recruiting further participants. "
        "Guaranteed large returns depend on continued recruitment.",
    ),
    ("Ling.csv", 674): (
        "uncertain",
        "Advertisement claiming guaranteed subliminal control over "
        "romantic or sexual attraction. Implausible guarantees raise "
        "deceptive-sales concerns. Ordinary spam versus fraud remains "
        "unresolved; the linked site was not visited.",
    ),
    ("Ling.csv", 706): (
        "ordinary_spam",
        "Apparent bulk promotion for debt-planning software with "
        "exaggerated financial promises. No explicit credential request "
        "or fraudulent transfer mechanism is shown. Claims are unverified.",
    ),
    ("Nazario.csv", 1044): (
        "uncertain",
        "Quarantine digest asking the recipient to release messages. "
        "Genuine notifications and phishing can share this format. "
        "Sender authentication and actual link destinations are unavailable.",
    ),
    ("Nazario.csv", 1243): (
        "phishing_or_fraud",
        "Apparent account-security phishing lure in Chinese. "
        "Asks the user to click to retain their password and threatens "
        "a changed password and lockout within 72 hours. "
        "Destination and sender identity are unverified.",
    ),
    ("Nazario.csv", 56): (
        "phishing_or_fraud",
        "Apparent PayPal impersonation requesting passwords, card details, "
        "CVV, and security codes. Unrelated French survey text is mixed "
        "into the body. Form destination is unavailable.",
    ),
    ("Nigerian_Fraud.csv", 2331): (
        "phishing_or_fraud",
        "Apparent inheritance-transfer scam asking a stranger to pose "
        "as next of kin, provide personal details and an account, "
        "and split a large deposit. Requests secrecy.",
    ),
    ("Nigerian_Fraud.csv", 826): (
        "phishing_or_fraud",
        "Apparent fraudulent fund-transfer solicitation claiming proceeds "
        "from inflated government contracts and offering a commission "
        "for use of the recipient's account.",
    ),
    ("Nigerian_Fraud.csv", 2971): (
        "uncertain",
        "Suspicious approach invoking illness, banking experience, urgency, "
        "secrecy, and mutual benefit. The actual transaction is withheld. "
        "Possible fraud grooming, but insufficient explicit evidence.",
    ),
    ("SpamAssasin.csv", 2662): (
        "legitimate",
        "Linux user-group discussion about restoring a boot record. "
        "No apparent phishing or fraud request. "
        "Quoted commands were not executed.",
    ),
    ("SpamAssasin.csv", 2873): (
        "legitimate",
        "Linux RAID troubleshooting discussion with configuration "
        "and boot logs. No apparent fraud request. "
        "Quoted commands were not executed.",
    ),
    ("SpamAssasin.csv", 2233): (
        "legitimate",
        "Brief news-feed style summary of a medical news story. "
        "No apparent promotion or fraud request. "
        "Article accuracy and link safety were not verified.",
    ),
    ("SpamAssasin.csv", 4954): (
        "ordinary_spam",
        "Base64 body decoded locally during review: advertises septic-system "
        "information and a free trial. No explicit phishing request. "
        "Consent, claims, and link safety are unverified. "
        "Original encoded body is preserved.",
    ),
    ("SpamAssasin.csv", 4545): (
        "uncertain",
        "Subject promises payment for watching advertisements, but the "
        "main offer is a remote image absent from the supplied text. "
        "The marketing footer cannot establish whether this is spam "
        "or a scam. The image was not loaded.",
    ),
    ("SpamAssasin.csv", 5014): (
        "ordinary_spam",
        "Apparent bulk mortgage promotion with broad approval claims. "
        "No explicit credential or payment request is shown. "
        "Link destinations, consent, and lender identity are unverified.",
    ),
}

def main():
    project_root = Path(__file__).resolve().parent.parent
    file_path = project_root / "data" / "private" / "review_samples.json"
    backup_path = file_path.with_name("review_samples.before_remaining_23.json")

    if not file_path.is_file():
        raise FileNotFoundError(
            f"Cannot find {file_path}. "
            "Save this script inside your project's training folder."
        )

    original_bytes = file_path.read_bytes()
    records = json.loads(original_bytes)

    if not isinstance(records, list) or len(records) != 30:
        raise ValueError(
            "Expected a JSON list containing 30 records. Nothing saved."
        )

    matched = []
    changed = 0
    already_reviewed = 0

    for record in records:
        key = (record["source"], record["record_number"])

        if key not in updates:
            continue

        matched.append(key)

        if record.get("reviewed_category") is not None:
            already_reviewed += 1
            continue

        if record.get("review_notes", "").strip():
            raise ValueError(
                f"{key} already has notes but no category. "
                "Review that entry before continuing. Nothing saved."
            )

        category, notes = updates[key]
        record["reviewed_category"] = category
        record["review_notes"] = notes
        changed += 1

    if sorted(matched) != sorted(updates):
        raise ValueError(
            "Some target records are missing or duplicated. Nothing saved."
        )

    if changed:
        if not backup_path.exists():
            with backup_path.open("xb") as file:
                file.write(original_bytes)

        updated_text = json.dumps(
            records,
            ensure_ascii=False,
            indent=2,
        ) + "\n"

        temporary_path = file_path.with_suffix(".tmp")
        temporary_path.write_text(updated_text, encoding="utf-8")
        temporary_path.replace(file_path)

    counts = Counter(
        record.get("reviewed_category") for record in records
    )

    print("New reviews saved:", changed)
    print("Target records already reviewed:", already_reviewed)
    print("Reviewed so far:", len(records) - counts[None])
    print("Total records preserved:", len(records))

    for category in (
        "legitimate",
        "ordinary_spam",
        "phishing_or_fraud",
        "uncertain",
    ):
        print(f"{category}: {counts[category]}")


if __name__ == "__main__":
    main()