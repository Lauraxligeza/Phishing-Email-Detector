import json
from collections import Counter
from html.parser import HTMLParser
from pathlib import Path


class TextExtractor(HTMLParser):
    SKIP = {"head", "script", "style", "template"}

    BLOCK = {
        "p", "div", "br", "hr", "li", "ul", "ol",
        "table", "tr", "td", "th",
        "h1", "h2", "h3", "h4", "h5", "h6",
        "blockquote", "pre", "section", "article",
    }

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []
        self.skipped = []
        self.images = 0

    def handle_starttag(self, tag, attrs):
        if tag in self.SKIP:
            self.parts.append("\n")
            self.skipped.append(tag)
            return

        if self.skipped:
            return

        if tag in self.BLOCK:
            self.parts.append("\n")

        if tag == "img":
            self.images += 1

    def handle_endtag(self, tag):
        if self.skipped:
            if tag in self.skipped:
                index = (
                    len(self.skipped)
                    - 1
                    - self.skipped[::-1].index(tag)
                )
                del self.skipped[index:]
            return

        if tag in self.BLOCK:
            self.parts.append("\n")

    def handle_data(self, data):
        if not self.skipped:
            self.parts.append(data)

    def text(self):
        return " ".join("".join(self.parts).split())


def extract_text(html):
    parser = TextExtractor()

    warnings = [
        "Approximate text extraction; CSS visibility is not evaluated.",
        "Head, script, style, template and comment content are excluded.",
    ]

    try:
        parser.feed(html)
        parser.close()
        text = parser.text()

        if parser.images:
            warnings.append(
                "Images were not loaded; image text and alt text "
                "are not included."
            )

        if parser.skipped:
            warnings.append(
                "An excluded HTML section was not closed; "
                "extracted text may be incomplete."
            )
            status = "needs_review"
        elif text:
            status = "extracted"
        else:
            status = "empty"
            warnings.append(
                "No text was recovered. This does not establish "
                "that the email has no meaningful content."
            )

        return text, status, warnings, parser.images

    except (ValueError, AssertionError) as error:
        warnings.append(
            "HTML parsing failed: " + type(error).__name__
        )
        return None, "needs_review", warnings, parser.images


def main():
    root = Path(__file__).resolve().parent.parent
    directory = root / "data" / "processed"

    input_path = directory / "emails_bodies_decoded.jsonl"
    output_path = directory / "emails_text_extracted.jsonl"
    temporary_path = output_path.with_suffix(".tmp")

    counts = Counter()
    total = 0

    print("Extracting text from recovered HTML...", flush=True)

    with (
        input_path.open(encoding="utf-8") as source,
        temporary_path.open("w", encoding="utf-8") as target,
    ):
        for line in source:
            record = json.loads(line)
            total += 1

            record["html_text_candidate"] = None
            record["html_text_status"] = "not_processed"
            record["html_text_warnings"] = []
            record["html_image_count"] = None

            if record["body_decode_status"] == "html_ready":
                html = record["body_html_candidate"]

                if not isinstance(html, str):
                    raise ValueError(
                        "An html_ready record has no HTML string."
                    )

                text, status, warnings, images = extract_text(html)

                record["html_text_candidate"] = text
                record["html_text_status"] = status
                record["html_text_warnings"] = warnings
                record["html_image_count"] = images

                counts[status] += 1

            target.write(
                json.dumps(record, ensure_ascii=False) + "\n"
            )

    temporary_path.replace(output_path)

    print("Records preserved:", total)
    print("HTML records processed:", sum(counts.values()))
    print("Text extracted:", counts["extracted"])
    print("No text recovered:", counts["empty"])
    print("Parsing needs review:", counts["needs_review"])
    print("Saved to:", output_path)


if __name__ == "__main__":
    main()