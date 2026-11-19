from html import escape
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs

import joblib

MODEL = Path(__file__).resolve().parent / "models/category_pilot_v2/model.joblib"
LABELS = {
    "legitimate": "Legitimate-like",
    "ordinary_spam": "Ordinary spam-like",
    "phishing_or_fraud": "Phishing or fraud-like",
}
PAGE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Email checker</title><style>
*{box-sizing:border-box}body{margin:0;background:#eef3f3;color:#153137;font:16px/1.55 Inter,system-ui,sans-serif}
main{max-width:700px;margin:7vh auto;padding:clamp(22px,5vw,50px);background:white;border-top:5px solid #16776e;border-radius:8px}
h1{font-size:clamp(32px,6vw,48px);letter-spacing:-.045em;line-height:1.1;margin:0}
p{color:#435a60}label{display:block;font-weight:650;margin:22px 0 6px}
input,textarea{display:block;width:100%;padding:12px;border:1px solid #869a9e;border-radius:5px;font:inherit}
textarea{resize:vertical}button{background:#125c54;color:white;border:0;border-radius:5px;padding:11px 23px;font:inherit;font-weight:bold;cursor:pointer}
.actions{display:flex;align-items:center;gap:20px;margin:18px 0}a{color:#165b56}
aside{padding:16px;background:#eef4f4;border-left:4px solid #437575}small{color:#435a60}
</style></head><body><main><h1>Email checker</h1><p>Paste an email to classify its wording with your local model.</p>
<form method="post" action="/" autocomplete="off"><label for="subject">Subject (optional)</label>
<input id="subject" name="subject" value="{subject}"><label for="body">Email body</label>
<textarea id="body" name="body" rows="8" required>{body}</textarea>
<div class="actions"><button>Analyze</button><a href="/">Clear</a></div></form>{result}
</main></body></html>"""


class Checker(BaseHTTPRequestHandler):
    def render(self, subject="", body="", message="", status=200):
        result = "<aside role='status'>" + escape(message) + "</aside>" if message else ""
        page = PAGE.replace("{result}", result).split("{subject}")
        before_body, after_body = page[1].split("{body}")
        data = (page[0] + escape(subject) + before_body + escape(body) + after_body).encode()
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Security-Policy", "default-src 'none'; style-src 'unsafe-inline'; form-action 'self'; frame-ancestors 'none'")
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if self.path != "/":
            return self.send_error(404)
        self.render()

    def do_POST(self):
        if self.path != "/":
            return self.send_error(404)
        if self.headers.get_content_type() != "application/x-www-form-urlencoded":
            return self.send_error(415)
        try:
            size = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            return self.send_error(400)
        if not 0 <= size <= 3_100_000:
            return self.send_error(413)
        form = parse_qs(self.rfile.read(size).decode("utf-8"), keep_blank_values=True)
        subject = form.get("subject", [""])[0]
        body = form.get("body", [""])[0]
        text = subject.strip() + "\n\n" + body.strip()
        if not body.strip():
            return self.render(subject, body, "Paste an email body first.", 400)
        if len(text.encode()) > 1_000_000:
            return self.render(message="Please use a shorter excerpt (1 MB maximum).", status=413)
        features = self.server.model[0].transform([text])
        if features.nnz:
            label = self.server.model[-1].predict(features)[0]
            message = "Predicted category: " + LABELS[label]
        else:
            message = "Too little recognizable text for a prediction."
        self.render(subject, body, message)


if __name__ == "__main__":
    if not MODEL.is_file():
        raise SystemExit(f"Place this script in your project root. Expected model at {MODEL}")
    model = joblib.load(MODEL)
    if set(model.classes_) != set(LABELS):
        raise SystemExit("Expected the three-category pilot model.")
    with ThreadingHTTPServer(("127.0.0.1", 8765), Checker) as server:
        server.model = model
        print("Open http://127.0.0.1:8765 in Brave. Press Ctrl+C here to stop.", flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
