#!/usr/bin/env python3
"""Small, dependency-free SEO inventory for code-based websites."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

PRIVATE_SEGMENTS = {"api", "admin", "painel", "account", "login", "my", "test", "thankyou"}
PAGE_RE = re.compile(r"(?:^|/)page\.(?:tsx?|jsx?)$")
METADATA_RE = re.compile(r"(?:export\s+(?:const\s+metadata|async\s+function\s+generateMetadata)|generateMetadata)")
NOINDEX_RE = re.compile(r"noindex|index:\s*false", re.IGNORECASE)
CANONICAL_RE = re.compile(r"canonical|alternates", re.IGNORECASE)
JSON_LD_RE = re.compile(r'application/ld\+json')
IMAGE_RE = re.compile(r"<img\b", re.IGNORECASE)
ALT_RE = re.compile(r"\balt\s*=", re.IGNORECASE)
HREF_RE = re.compile(r"href\s*=\s*(?:\{\s*)?[\"']([^\"'#]+)", re.IGNORECASE)
TITLE_VALUE_RE = re.compile(r"\btitle\s*:\s*[\"']([^\"']+)[\"']", re.IGNORECASE)
DESCRIPTION_VALUE_RE = re.compile(r"\bdescription\s*:\s*[\"']([^\"']+)[\"']", re.IGNORECASE)
H1_RE = re.compile(r"<h1\b", re.IGNORECASE)
JSON_LD_BLOCK_RE = re.compile(r"<script[^>]*application/ld\+json[^>]*>(.*?)</script>", re.IGNORECASE | re.DOTALL)
SCHEMA_TYPE_RE = re.compile(r"[\"']@type[\"']\s*:\s*[\"']([^\"']+)[\"']")


def route_for(path: Path, app_root: Path) -> str:
    relative = path.relative_to(app_root).parent.parts
    segments = [segment for segment in relative if not segment.startswith("[")]
    return "/" + "/".join(segments)


def is_private(route: str) -> bool:
    return any(segment in PRIVATE_SEGMENTS for segment in route.strip("/").split("/"))


def source_with_layouts(path: Path, app_root: Path) -> str:
    """Include metadata inherited from the App Router's ancestor layouts."""
    sources = []
    current = path.parent
    while True:
        for suffix in (".tsx", ".ts", ".jsx", ".js"):
            layout = current / f"layout{suffix}"
            if layout.is_file():
                sources.append(layout.read_text(encoding="utf-8", errors="replace"))
                break
        if current == app_root:
            break
        if app_root not in current.parents:
            break
        current = current.parent
    return "\n".join(sources)


def has_route_layout(path: Path, app_root: Path) -> bool:
    current = path.parent
    while current != app_root:
        if any((current / f"layout{suffix}").is_file() for suffix in (".tsx", ".ts", ".jsx", ".js")):
            return True
        current = current.parent
    return False


def internal_targets(text: str) -> set[str]:
    targets = set()
    for href in HREF_RE.findall(text):
        if not href.startswith("/") or href.startswith("//"):
            continue
        target = href.split("?", 1)[0].rstrip("/") or "/"
        if not is_private(target):
            targets.add(target)
    return targets


def source_files(root: Path) -> list[Path]:
    return [
        path for path in (root / "src").rglob("*")
        if path.is_file() and path.suffix in {".ts", ".tsx", ".js", ".jsx"}
    ]


def literal_length(pattern: re.Pattern[str], text: str) -> int | None:
    match = pattern.search(text)
    return len(match.group(1).strip()) if match else None


def inspect_json_ld(text: str) -> tuple[list[str], list[str]]:
    schema_types: list[str] = []
    issues: list[str] = []
    for block in JSON_LD_BLOCK_RE.findall(text):
        schema_types.extend(item for item in SCHEMA_TYPE_RE.findall(block) if item not in schema_types)
        candidate = block.strip()
        if not candidate.startswith(("{", "[")):
            continue
        try:
            parsed = json.loads(candidate)
        except json.JSONDecodeError:
            issues.append("invalid JSON")
            continue
        objects = parsed if isinstance(parsed, list) else [parsed]
        for item in objects:
            if not isinstance(item, dict):
                issues.append("JSON-LD root is not an object")
                continue
            if "@context" not in item:
                issues.append("missing @context")
            if "@type" not in item:
                issues.append("missing @type")
    return schema_types, issues


def audit(root: Path) -> dict[str, object]:
    app_root = root / "src" / "app"
    if not app_root.is_dir():
        return {"framework": "unknown", "pages": [], "warnings": ["src/app was not found"]}

    pages: list[dict[str, object]] = []
    for path in sorted(app_root.rglob("page.*")):
        if not PAGE_RE.search(path.as_posix()) or path.suffix not in {".ts", ".tsx", ".js", ".jsx"}:
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        effective_text = f"{source_with_layouts(path, app_root)}\n{text}"
        quality_text = effective_text if route_for(path, app_root) == "/" or has_route_layout(path, app_root) else text
        route = route_for(path, app_root)
        private = is_private(route)
        schema_types, json_ld_issues = inspect_json_ld(effective_text)
        image_count = len(IMAGE_RE.findall(text))
        alt_count = len(ALT_RE.findall(text))
        pages.append({
            "route": route or "/",
            "file": path.relative_to(root).as_posix(),
            "private": private,
            "has_metadata": bool(METADATA_RE.search(effective_text)),
            "has_canonical": bool(CANONICAL_RE.search(effective_text)),
            "noindex": bool(NOINDEX_RE.search(effective_text)),
            "has_json_ld": bool(JSON_LD_RE.search(effective_text)),
            "schema_types": schema_types,
            "json_ld_issues": json_ld_issues,
            "images": image_count,
            "images_with_alt": min(image_count, alt_count),
            "title_length": literal_length(TITLE_VALUE_RE, quality_text),
            "description_length": literal_length(DESCRIPTION_VALUE_RE, quality_text),
            "h1_count": len(H1_RE.findall(text)),
        })

    public = [page for page in pages if not page["private"]]
    public_routes = {page["route"].rstrip("/") or "/" for page in public}
    broken_internal_links: list[dict[str, str]] = []
    linked_public_routes: set[str] = {"/"}
    public_page_files = {root / str(page["file"]): str(page["route"]) for page in public}
    has_dynamic_links = False
    for path in source_files(root):
        text = path.read_text(encoding="utf-8", errors="replace")
        has_dynamic_links = has_dynamic_links or bool(re.search(r"href\s*=\s*\{", text, re.IGNORECASE))
        source = public_page_files.get(path, path.relative_to(root).as_posix())
        for target in internal_targets(text):
            if target in public_routes:
                linked_public_routes.add(target)
            else:
                broken_internal_links.append({"source": source, "target": target})
    # Dynamic navigation maps cannot be resolved safely with regex alone.
    orphan_public_routes = [] if has_dynamic_links else sorted(public_routes - linked_public_routes)
    warnings: list[str] = []
    for page in public:
        if not page["has_metadata"] and page["route"] != "/":
            warnings.append(f"missing metadata: {page['route']}")
        if not page["has_canonical"] and page["route"] != "/":
            warnings.append(f"missing canonical: {page['route']}")
        if page["images"] != page["images_with_alt"]:
            warnings.append(f"image alt text needs review: {page['route']}")
        if page["title_length"] is not None and not 30 <= page["title_length"] <= 60:
            label = "too short" if page["title_length"] < 30 else "too long"
            warnings.append(f"title {label}: {page['route']}")
        if page["description_length"] is not None and not 70 <= page["description_length"] <= 160:
            label = "too short" if page["description_length"] < 70 else "too long"
            warnings.append(f"description {label}: {page['route']}")
        if page["h1_count"] > 1:
            warnings.append(f"expected one H1, found {page['h1_count']}: {page['route']}")
        if page["json_ld_issues"]:
            warnings.append(f"invalid JSON-LD: {page['route']}")
    for page in pages:
        if page["private"] and not page["noindex"]:
            warnings.append(f"private route may be indexable: {page['route']}")
    warnings.extend(f"broken internal link: {item['source']} -> {item['target']}" for item in broken_internal_links)
    warnings.extend(f"orphan public route: {route}" for route in orphan_public_routes)

    return {
        "framework": "next-app-router",
        "root": str(root),
        "pages": pages,
        "broken_internal_links": broken_internal_links,
        "orphan_public_routes": orphan_public_routes,
        "link_analysis_limited": has_dynamic_links,
        "summary": {"total_pages": len(pages), "public_pages": len(public), "warnings": len(warnings)},
        "warnings": warnings,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit technical SEO signals in a code-based website")
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--format", choices={"text", "json"}, default="text")
    args = parser.parse_args()
    result = audit(args.root.resolve())
    if args.format == "json":
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0
    summary = result.get("summary", {})
    print(f"SEO audit: {result['framework']}")
    print(f"Pages: {summary.get('total_pages', 0)} total, {summary.get('public_pages', 0)} public")
    warnings = result.get("warnings", [])
    print(f"Warnings: {len(warnings)}")
    for warning in warnings:
        print(f"- {warning}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
