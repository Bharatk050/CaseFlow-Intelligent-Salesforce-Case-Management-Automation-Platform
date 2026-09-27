"""Local, explainable retrieval for the Roster Support knowledge base."""

from __future__ import annotations

import re
from pathlib import Path


REFERENCE_SLUGS = {
    "README", "SKILL", "guardrails", "glossary", "escalation-and-routing",
    "link-registry", "open-questions",
}


def document_slug(path: Path) -> str:
    return path.name.removesuffix(".md.txt").removesuffix(".md")


def _tokens(text: str) -> set[str]:
    return {token.lower() for token in re.findall(r"[a-zA-Z][a-zA-Z0-9_-]{2,}", text)}


def metadata(content: str) -> dict[str, str]:
    if not content.startswith("---"):
        return {}
    header = content.split("---", 2)[1]
    return {
        key.strip(): value.strip().strip('"')
        for line in header.splitlines() if ":" in line
        for key, value in [line.split(":", 1)]
    }


def aliases(content: str) -> list[str]:
    raw = metadata(content).get("aliases", "")
    return [value.lower() for value in re.findall(r'"([^"]+)"', raw)]


def retrieve_articles(help_center_dir: Path, query: str, limit: int = 3) -> list[dict]:
    """Rank case playbooks using their declared case type and aliases."""
    normalized_query = " ".join(query.lower().split())
    query_terms = _tokens(normalized_query)
    matches: list[dict] = []
    paths = sorted({*help_center_dir.glob("*.md"), *help_center_dir.glob("*.md.txt")})
    for path in paths:
        slug = document_slug(path)
        if slug in REFERENCE_SLUGS:
            continue
        content = path.read_text(encoding="utf-8")
        title = next((line.removeprefix("# ").strip() for line in content.splitlines() if line.startswith("# ")), slug)
        header = metadata(content)
        declared_aliases = aliases(content)
        matched_aliases = [alias for alias in declared_aliases if alias in normalized_query]
        title_terms = _tokens(f"{title} {header.get('case_type', '')}")
        body_terms = _tokens(content)
        # Case playbooks share generic vocabulary. Alias phrases are therefore the
        # strongest signal, followed by case type/title, then body overlap.
        raw_score = 10 * len(matched_aliases) + 4 * len(query_terms & title_terms) + len(query_terms & body_terms)
        score = raw_score / max(len(query_terms), 1)
        if score:
            matches.append({
                "slug": slug,
                "title": title,
                "content": content,
                "metadata": header,
                "matched_aliases": matched_aliases,
                "score": round(score, 3),
                "raw_score": raw_score,
            })
    return sorted(matches, key=lambda article: (-article["raw_score"], article["slug"]))[:limit]
