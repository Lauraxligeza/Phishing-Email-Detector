import hashlib
import json
import platform
import re
import tempfile
import unicodedata
from collections import Counter, defaultdict
from functools import lru_cache
from importlib.metadata import version
from pathlib import Path

from datasketch import MinHash, MinHashLSH


SEED = 42
NUM_PERM = 128
SEARCH_THRESHOLD = 0.70
MATCH_THRESHOLD = 0.85
MAX_CHARACTERS = 60000
MIN_WORDS = 30
SPLITS = ("train", "validation", "test")


def digest(value):
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def build_splits(input_path, output_path):
    if output_path.exists():
        raise FileExistsError(f"{output_path} already exists. Nothing overwritten.")

    rows = []
    identities = set()
    input_hash = hashlib.sha256()
    print("Reading prepared records...", flush=True)

    with input_path.open("rb") as file:
        for line in file:
            input_hash.update(line)
            record = json.loads(line)
            key = (record["source"], record["record_number"])
            if key in identities:
                raise ValueError(f"Duplicate record identity: {key}")
            identities.add(key)
            eligible = record["baseline_eligible"]
            label = record["baseline_label"]
            text = record["model_text_candidate"]
            if type(eligible) is not bool or type(label) is not int or label not in (0, 1):
                raise ValueError(f"Invalid eligibility or label: {key}")
            if eligible and (not isinstance(text, str) or not text.strip()):
                raise ValueError(f"Eligible record has no model text: {key}")
            if eligible and not record["prepared_text_group"]:
                raise ValueError(f"Eligible record has no prepared group: {key}")
            grouping_text = text or (record["subject"] + "\n\n" + record["body"])
            rows.append({
                "source": key[0], "record_number": key[1], "label": label,
                "eligible": eligible, "text": text, "grouping_text": grouping_text,
                "raw_group": record["duplicate_group"],
                "prepared_group": record["prepared_text_group"],
                "reviewed": record.get("reviewed_category") is not None
                or record["split_constraint"] == "development_only",
                "flags": record["preparation_flags"],
            })

    if not rows:
        raise ValueError("Input is empty.")
    rows.sort(key=lambda row: (row["source"], row["record_number"]))
    parent = list(range(len(rows)))

    def find(index):
        while parent[index] != index:
            parent[index] = parent[parent[index]]
            index = parent[index]
        return index

    def union(left, right):
        left, right = find(left), find(right)
        if left != right:
            parent[max(left, right)] = min(left, right)

    seen = {}
    for index, row in enumerate(rows):
        for field in ("raw_group", "prepared_group"):
            if row[field]:
                key = (field, row[field])
                if key in seen:
                    union(index, seen[key])
                else:
                    seen[key] = index

    @lru_cache(maxsize=128)
    def shingles(index):
        words = rows[index]["normalized"].split()
        return {" ".join(words[pos:pos + 5]) for pos in range(len(words) - 4)}

    indexer = MinHashLSH(threshold=SEARCH_THRESHOLD, num_perm=NUM_PERM)
    normalized_seen = {}
    counts = Counter()
    near_pairs = []
    print("Grouping similar text; progress every 2,000 records...", flush=True)

    for index, row in enumerate(rows):
        if index and index % 2000 == 0:
            print(f"Grouped {index:,} / {len(rows):,}", flush=True)
        text = row.pop("grouping_text")
        normalized = " ".join(re.findall(r"\w+", unicodedata.normalize("NFKC", text).casefold()))
        row["normalized"] = normalized
        row["similarity_skipped"] = None
        if normalized:
            key = digest(normalized)
            if key in normalized_seen:
                union(index, normalized_seen[key])
                counts["normalized_exact_copies"] += 1
                continue
            normalized_seen[key] = index

        if len(text) > MAX_CHARACTERS:
            row["similarity_skipped"] = "long_text"
        elif len(normalized.split()) < MIN_WORDS:
            row["similarity_skipped"] = "short_text"

        if row["similarity_skipped"]:
            counts[row["similarity_skipped"]] += 1
            continue

        pieces = shingles(index)
        signature = MinHash(num_perm=NUM_PERM, seed=SEED)
        ordered = sorted(pieces)
        for start in range(0, len(ordered), 256):
            signature.update_batch([item.encode("utf-8") for item in ordered[start:start + 256]])

        for other in sorted(indexer.query(signature)):
            counts["candidate_pairs_checked"] += 1
            other_pieces = shingles(other)
            similarity = len(pieces & other_pieces) / len(pieces | other_pieces)
            if similarity >= MATCH_THRESHOLD:
                union(index, other)
                near_pairs.append((index, other, round(similarity, 6)))
        indexer.insert(index, signature)
        counts["signatures_indexed"] += 1

    shingles.cache_clear()
    del indexer
    groups = defaultdict(list)
    for index, row in enumerate(rows):
        row.pop("normalized")
        groups[find(index)].append(index)

    assignments = {}
    forced = set()
    group_ids = {}
    for root, members in groups.items():
        first = rows[root]
        group_id = digest(json.dumps([first["source"], first["record_number"]]))
        group_ids[root] = group_id
        if any(rows[i]["reviewed"] or rows[i]["similarity_skipped"] for i in members):
            forced.add(root)
            assignments[root] = "train"
        else:
            fraction = int(digest(f"{SEED}:{group_id}")[:16], 16) / 2**64
            assignments[root] = "train" if fraction < 0.8 else "validation" if fraction < 0.9 else "test"

    representatives = {}
    split_counts = {name: Counter() for name in SPLITS}
    source_counts = {name: Counter() for name in SPLITS}
    manifest = []
    selected = []
    for index, row in enumerate(rows):
        root = find(index)
        entry = {
            "source": row["source"], "record_number": row["record_number"],
            "group_id": group_ids[root], "group_split": assignments[root],
            "similarity_skipped": row["similarity_skipped"],
            "split": None, "duplicate_of": None,
        }
        if not row["eligible"]:
            entry["status"] = "excluded"
            entry["reasons"] = row["flags"]
        elif row["prepared_group"] in representatives:
            other = representatives[row["prepared_group"]]
            if row["label"] != other["label"]:
                raise ValueError("Eligible prepared duplicates have conflicting labels.")
            entry["status"] = "duplicate_copy"
            entry["duplicate_of"] = [other["source"], other["record_number"]]
        else:
            representatives[row["prepared_group"]] = row
            split = assignments[root]
            entry["status"] = "selected"
            entry["split"] = split
            selected.append((index, split))
            split_counts[split][str(row["label"])] += 1
            source_counts[split][row["source"]] += 1
        manifest.append(entry)

    for split in SPLITS:
        if set(split_counts[split]) != {"0", "1"}:
            raise ValueError(f"{split} does not contain both labels; inspect grouping before training.")
    if any(assignments[find(i)] != "train" for i, row in enumerate(rows) if row["reviewed"]):
        raise AssertionError("Reviewed material reached evaluation.")
    for field in ("raw_group", "prepared_group"):
        observed = defaultdict(set)
        for index, split in selected:
            if rows[index][field]:
                observed[rows[index][field]].add(split)
        if any(len(splits) > 1 for splits in observed.values()):
            raise AssertionError(f"Duplicate leakage through {field}.")

    report = {
        "input_sha256": input_hash.hexdigest(),
        "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "versions": {"python": platform.python_version(), "datasketch": version("datasketch"), "numpy": version("numpy")},
        "settings": {"seed": SEED, "permutations": NUM_PERM, "search_threshold": SEARCH_THRESHOLD,
                     "verified_jaccard_threshold": MATCH_THRESHOLD, "shingle_words": 5,
                     "minimum_words": MIN_WORDS, "maximum_characters": MAX_CHARACTERS},
        "input_records": len(rows), "groups": len(groups),
        "record_status_counts": dict(Counter(entry["status"] for entry in manifest)),
        "similarity_counts": dict(counts), "verified_similar_pairs": len(near_pairs),
        "forced_training_groups": len(forced),
        "reviewed_records": sum(row["reviewed"] for row in rows),
        "mixed_label_groups": sum(len({rows[i]["label"] for i in members}) > 1 for members in groups.values()),
        "largest_group_sizes": sorted((len(members) for members in groups.values()), reverse=True)[:10],
        "split_label_counts": {name: dict(value) for name, value in split_counts.items()},
        "split_source_counts": {name: dict(value) for name, value in source_counts.items()},
        "limitations": [
            "Inherited binary labels do not distinguish ordinary spam from phishing or fraud.",
            "Approximate candidate search can miss similar pairs; these are text groups, not verified campaigns.",
            "Short and long texts skipped by similarity search force their whole group into training.",
            "Reviewed records and related groups are development material, never evaluation ground truth.",
            "Hash assignment targets 80/10/10 before training-only constraints; it is not stratified.",
            "Connected groups can contain pairs below the direct similarity threshold.",
            "This is an internal corpus benchmark, not a temporal or external generalization test.",
        ],
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=output_path.parent) as temporary:
        staged = Path(temporary) / "splits"
        staged.mkdir()
        for split in SPLITS:
            with (staged / f"{split}.jsonl").open("w", encoding="utf-8") as file:
                for index, assigned in selected:
                    if assigned == split:
                        row = rows[index]
                        output = {key: row[key] for key in ("source", "record_number", "label", "text")}
                        output["group_id"] = group_ids[find(index)]
                        file.write(json.dumps(output, ensure_ascii=False) + "\n")
        with (staged / "manifest.jsonl").open("w", encoding="utf-8") as file:
            for entry in manifest:
                file.write(json.dumps(entry, ensure_ascii=False) + "\n")
        with (staged / "similar_pairs.jsonl").open("w", encoding="utf-8") as file:
            for left, right, similarity in near_pairs:
                pair = {"left": [rows[left]["source"], rows[left]["record_number"]],
                        "right": [rows[right]["source"], rows[right]["record_number"]], "jaccard": similarity}
                file.write(json.dumps(pair) + "\n")
        write_json(staged / "split_report.json", report)
        staged.rename(output_path)

    print("Records accounted for:", len(manifest))
    print("Record status counts:", report["record_status_counts"])
    print("Related text groups:", len(groups))
    print("Verified similar pairs:", len(near_pairs))
    print("Groups restricted to training:", len(forced))
    for split in SPLITS:
        print(f"{split}: {sum(split_counts[split].values())} records; labels {dict(split_counts[split])}")
    print("Saved to:", output_path)


def main():
    root = Path(__file__).resolve().parent.parent
    build_splits(root / "data/processed/emails_prepared.jsonl", root / "data/splits")


if __name__ == "__main__":
    main()