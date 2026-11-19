import base64
import json
import quopri
import re
from collections import Counter
from email import policy
from email.errors import MessageError
from email.parser import Parser
from pathlib import Path


CANDIDATE = re.compile(
    r"^[ \t]*Content-Transfer-Encoding:",
    re.IGNORECASE | re.MULTILINE,
)

BOUNDARY = re.compile(
    r"^--([^\r\n]+)\r?\n(?=Content-Type:)",
    re.IGNORECASE | re.MULTILINE,
)

MIME_NOTICE = re.compile(
    r"^This (?:is a|message is in) "
    r"(?:multi[ -]?part(?: MIME)? message|MIME format)",
    re.IGNORECASE,
)


def decode_body(body):
    result = {
        "body_text_candidate": body,
        "body_html_candidate": None,
        "body_decode_status": "unchanged",
        "body_decode_method": "no_candidate_header",
        "body_decode_warnings": [],
    }

    if not CANDIDATE.search(body):
        return result

    warnings = result["body_decode_warnings"]

    def unresolved(reason):
        result["body_decode_status"] = "needs_review"
        warnings.append(reason)
        return result

    try:
        parser = Parser(policy=policy.default)
        message = parser.parsestr(body.lstrip("\r\n"))
        inferred = False
        result["body_decode_method"] = "declared_mime"

        if message.get("Content-Type") is None:
            match = BOUNDARY.search(body)

            if match is None:
                return unresolved(
                    "Embedded or quoted headers; "
                    "no recoverable leading MIME boundary."
                )

            prefix = body[:match.start()].strip()

            if prefix and (
                len(prefix) > 600 or not MIME_NOTICE.match(prefix)
            ):
                return unresolved(
                    "MIME occurs after ordinary text; "
                    "preserve the full body for review."
                )

            boundary = match.group(1).rstrip(" \t")

            if (
                len(boundary) > 70
                or boundary.endswith("--")
                or not re.fullmatch(r"[ -~]+", boundary)
                or '"' in boundary
                or "\\" in boundary
            ):
                return unresolved(
                    "Boundary cannot be reconstructed conservatively."
                )

            wrapper = (
                'MIME-Version: 1.0\n'
                'Content-Type: multipart/mixed; boundary="'
                + boundary
                + '"\n\n'
            )

            message = parser.parsestr(
                wrapper + body[match.start():]
            )

            inferred = True
            result["body_decode_method"] = "inferred_boundary"

            warnings.append(
                "Outer MIME wrapper inferred from a leading boundary; "
                "original subtype is unknown."
            )

            if prefix:
                warnings.append(
                    "Leading MIME notice omitted from the candidate; "
                    "original body retained."
                )

        for item in message.walk():
            for defect in item.defects:
                name = type(defect).__name__

                if inferred and name == "CloseBoundaryNotFoundDefect":
                    warnings.append(
                        "Closing boundary missing; "
                        "recovered content may be incomplete."
                    )
                else:
                    return unresolved(
                        "MIME structure defect: " + name
                    )

            for name in (
                "Content-Type",
                "Content-Transfer-Encoding",
                "Content-Disposition",
            ):
                values = item.get_all(name, [])

                if len(values) > 1 or any(
                    getattr(value, "defects", ())
                    for value in values
                ):
                    return unresolved(
                        "Ambiguous or malformed MIME headers."
                    )

        part = message.get_body(
            preferencelist=("plain", "html")
        )

        if part is None or part.get_filename():
            return unresolved(
                "No selectable inline text body; "
                "attachments are excluded."
            )

        if part.get("Content-Type") is None:
            return unresolved(
                "Selected part has no explicit Content-Type."
            )

        payload = part.get_payload(decode=False)

        if not isinstance(payload, str):
            return unresolved(
                "Selected payload is not a text string."
            )

        if CANDIDATE.match(payload.lstrip("\r\n")):
            return unresolved(
                "An encoding header appears after "
                "the header/body separator."
            )

        encoding = str(
            part.get("Content-Transfer-Encoding", "7bit")
        ).strip().lower()

        if encoding == "base64":
            compact = re.sub(r"[ \t\r\n]", "", payload)

            raw = base64.b64decode(
                compact.encode("ascii"),
                validate=True,
            )

            text = raw.decode(
                part.get_content_charset() or "ascii",
                errors="strict",
            )

        elif encoding == "quoted-printable":
            if re.search(
                r"=(?![0-9A-Fa-f]{2}|\r?\n)",
                payload,
            ):
                return unresolved(
                    "Malformed quoted-printable escape."
                )

            raw = quopri.decodestring(
                payload.encode("ascii")
            )

            text = raw.decode(
                part.get_content_charset() or "ascii",
                errors="strict",
            )

        elif encoding in {"7bit", "8bit"}:
            text = payload

        else:
            return unresolved(
                "Unsupported transfer encoding: " + encoding
            )

        if message.is_multipart():
            warnings.append(
                "Selected one inline body; other MIME parts "
                "are excluded from this candidate."
            )

        if any(
            (item.epilogue or "").strip()
            for item in message.walk()
        ):
            warnings.append(
                "Text after a closing boundary is omitted "
                "from the candidate; original body retained."
            )

        if (message.preamble or "").strip():
            warnings.append(
                "MIME preamble is omitted from the candidate; "
                "original body retained."
            )

        if part.get_content_type() == "text/html":
            result["body_text_candidate"] = None
            result["body_html_candidate"] = text
            result["body_decode_status"] = "html_ready"

            warnings.append(
                "HTML stored as text only; "
                "plain-text extraction is still required."
            )

        else:
            result["body_text_candidate"] = text

            result["body_decode_status"] = (
                "decoded_plain"
                if encoding in {"base64", "quoted-printable"}
                else "extracted_plain"
            )

        result["body_decode_warnings"] = list(
            dict.fromkeys(warnings)
        )

        return result

    except (
        MessageError,
        ValueError,
        LookupError,
        UnicodeError,
        RecursionError,
    ) as error:
        return unresolved(
            "Body decoding failed: " + type(error).__name__
        )


def main():
    root = Path(__file__).resolve().parent.parent
    directory = root / "data" / "processed"

    input_path = directory / "emails_subjects_decoded.jsonl"
    output_path = directory / "emails_bodies_decoded.jsonl"
    temporary_path = output_path.with_suffix(".tmp")

    counts = Counter()
    methods = Counter()
    issues = Counter()

    print("Processing email bodies...", flush=True)

    with (
        input_path.open(encoding="utf-8") as source,
        temporary_path.open("w", encoding="utf-8") as target,
    ):
        for line in source:
            record = json.loads(line)
            record.update(decode_body(record["body"]))

            target.write(
                json.dumps(record, ensure_ascii=False) + "\n"
            )

            counts[record["body_decode_status"]] += 1
            methods[record["body_decode_method"]] += 1
            issues.update(record["body_decode_warnings"])

    temporary_path.replace(output_path)

    print("Records processed:", sum(counts.values()))

    for status in (
        "decoded_plain",
        "extracted_plain",
        "html_ready",
        "unchanged",
        "needs_review",
    ):
        print(f"{status}: {counts[status]}")

    print("\nWarnings:")

    for warning, count in issues.most_common():
        print(f"{count}: {warning}")

    print("\nSaved to:", output_path)


if __name__ == "__main__":
    main()