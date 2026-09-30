"""Local section retrieval with BM25, explicit document types and stable sources."""
from __future__ import annotations

import math
import os
import re
from collections import Counter
from pathlib import Path

REFERENCE_SLUGS = {"README", "SKILL", "guardrails", "glossary", "escalation-and-routing",
                   "link-registry", "open-questions", "roster-vs-technical-support", "salesforce-case-management"}
STOP_WORDS = set("a an the this that those these to for of in on at is are was were be been have has had and or but with from as it its we they their our my his her all please can could would should not no after before into need help issue request".split())
LEGACY_SLUGS = {"roster_vs_technical_support_overview": "roster-vs-technical-support",
                "salesforce_case_management_guide": "salesforce-case-management"}


def retrieve_evidence(root: Path, query: str, limit: int = 6) -> tuple[list[dict], str]:
    lexical = retrieve_articles(root, query, limit=100, references=True)
    if os.getenv("ENABLE_FAISS", "true").lower() != "true":
        return lexical[:limit], "lexical"
    try:
        try:
            from .vector_store import search
        except ImportError:
            from vector_store import search
        documents = load_documents(root)
        hits = search(documents, query)
    except (ImportError, OSError, RuntimeError, ValueError):
        return lexical[:limit], "lexical_fallback"
    ranked = {d["slug"]: dict(d, fusion_score=1 / (60 + i)) for i, d in enumerate(lexical, 1)}
    for i, ((slug, section_id), score) in enumerate(hits, 1):
        doc = next(d for d in documents if d["slug"] == slug)
        entry = ranked.setdefault(slug, dict(doc, matched_sections=[], matched_aliases=[], title_matches=0, score=score, fusion_score=0))
        entry["fusion_score"] += 1 / (60 + i)
        section = next(s for s in doc["sections"] if s["section_id"] == section_id)
        if not any(s["section_id"] == section_id for s in entry["matched_sections"]):
            entry["matched_sections"].append(section)
    return sorted(ranked.values(), key=lambda d: -d["fusion_score"])[:limit], "faiss_hybrid"


def document_slug(path: Path) -> str:
    return path.name.removesuffix(".md.txt").removesuffix(".md")


def canonical_slug(slug: str) -> str:
    slug = re.sub(r"(?:_additional|-1)$", "", slug)
    return LEGACY_SLUGS.get(slug, slug)


def tokens(text: str) -> list[str]:
    words = [word for word in re.findall(r"[a-z0-9_]+", text.lower()) if len(word) > 1 and word not in STOP_WORDS]
    roots = {"deactivation": "deactivate", "deactivated": "deactivate", "deactivating": "deactivate",
             "reactivation": "reactivate", "reactivated": "reactivate", "reactivating": "reactivate",
             "syncing": "sync", "synced": "sync", "syncs": "sync", "passwords": "password",
             "students": "student", "teachers": "teacher", "users": "user", "admins": "admin",
             "sections": "section", "classes": "class", "credentials": "credential", "filters": "filter"}
    return [roots.get(word, word) for word in words]


def metadata(content: str) -> dict[str, str]:
    if not content.startswith("---\n") or "\n---" not in content[4:]:
        return {}
    return {key.strip(): value.strip().strip('"')
            for line in content.split("---", 2)[1].splitlines() if ":" in line
            for key, value in [line.split(":", 1)]}


def aliases(content: str) -> list[str]:
    return [value.lower() for value in re.findall(r'"([^\"]+)"', metadata(content).get("aliases", ""))]


def document_paths(root: Path) -> list[Path]:
    return sorted(path for path in root.rglob("*")
                  if path.is_file() and (path.name.endswith(".md") or path.name.endswith(".md.txt"))
                  and not any(part.startswith(("_", ".")) for part in path.relative_to(root).parts))


def sections(content: str, slug: str) -> list[dict]:
    """Keep each H2 branch whole, including H3 conditions and ordered steps."""
    body = content.split("---", 2)[2] if content.startswith("---\n") else content
    chunks = re.split(r"(?m)^## ", body)
    result = []
    for index, chunk in enumerate(chunks):
        heading, _, text = chunk.strip().partition("\n")
        if not text.strip():
            continue
        heading = heading.lstrip("# ")
        anchor = re.sub(r"[^a-z0-9]+", "-", heading.lower()).strip("-") or "overview"
        result.append({"section_id": f"{slug}#{index}-{anchor}", "heading": heading,
                       "content": text.strip(), "order": index})
    return result


def load_documents(root: Path) -> list[dict]:
    result = []
    seen = set()
    for path in document_paths(root):
        content = path.read_text(encoding="utf-8-sig")
        slug = document_slug(path)
        if slug in seen:
            raise ValueError(f"Duplicate knowledge-base slug: {slug}")
        seen.add(slug)
        header = metadata(content)
        title = next((line[2:].strip() for line in content.splitlines() if line.startswith("# ")), slug)
        kind = header.get("type", "reference" if slug in REFERENCE_SLUGS else "case" if header.get("case_type") else "reference")
        result.append({"slug": slug, "title": title, "content": content, "metadata": header,
                       "type": kind, "path": path.relative_to(root).as_posix(),
                       "legacy_slugs": [slug + "_additional", slug + "-1"] + [old for old, new in LEGACY_SLUGS.items() if new == slug],
                       "sections": sections(content, slug)})
    return result


def retrieve_articles(help_center_dir: Path, query: str, limit: int = 3, *, subject: str = "", references: bool = False) -> list[dict]:
    """Description is primary; subject adds evidence but cannot force a router match."""
    docs = [doc for doc in load_documents(help_center_dir) if references or doc["type"] == "case"]
    corpus = [(doc, section, Counter(tokens(section["content"] + " " + section["heading"])))
              for doc in docs for section in doc["sections"]]
    if not corpus:
        return []
    avg_length = sum(sum(count.values()) for _, _, count in corpus) / len(corpus)
    frequencies = Counter(term for _, _, count in corpus for term in count)
    query_terms = set(tokens(query))
    subject_terms = set(tokens(subject))
    scored = {}
    normalized = " ".join(query.lower().split())
    normalized_terms = " " + " ".join(tokens(query)) + " "
    for doc, section, counts in corpus:
        length = sum(counts.values())
        score = 0.0
        for term in query_terms | subject_terms:
            frequency = counts[term]
            weight = 1.0 if term in query_terms else 0.2
            idf = math.log(1 + (len(corpus) - frequencies[term] + 0.5) / (frequencies[term] + 0.5))
            score += weight * idf * frequency * 2.2 / (frequency + 1.2 * (0.25 + 0.75 * length / max(avg_length, 1)))
        matched = [alias for alias in aliases(doc["content"]) if
                   re.search(r"(?<!\w)" + re.escape(alias) + r"(?!\w)", normalized)
                   or (len(tokens(alias)) >= 2 and " " + " ".join(tokens(alias)) + " " in normalized_terms)]
        title_overlap = query_terms & set(tokens(doc["title"] + " " + doc["metadata"].get("case_type", "")))
        bonus = 12 * len(matched) + 3 * len(title_overlap)
        entry = scored.setdefault(doc["slug"], {**doc, "matched_aliases": matched, "score": 0.0,
                                                 "raw_score": 0.0, "title_matches": len(title_overlap), "matched_sections": []})
        entry["matched_sections"].append({**section, "score": round(score, 3)})
        entry["score"] = entry["raw_score"] = max(entry["score"], round(score + bonus, 3))
    for entry in scored.values():
        entry["matched_sections"] = sorted(entry["matched_sections"], key=lambda section: (-section["score"], section["order"]))[:3]
    return sorted((entry for entry in scored.values() if entry["score"] > 0), key=lambda entry: (-entry["score"], entry["slug"]))[:limit]
