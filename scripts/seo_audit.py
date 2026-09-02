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
        route = route_for(path, app_root)
        private = is_private(route)
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
            "images": image_count,
            "images_with_alt": min(image_count, alt_count),
        })

    public = [page for page in pages if not page["private"]]
    warnings: list[str] = []
    for page in public:
        if not page["has_metadata"] and page["route"] != "/":
            warnings.append(f"missing metadata: {page['route']}")
        if not page["has_canonical"] and page["route"] != "/":
            warnings.append(f"missing canonical: {page['route']}")
        if page["images"] != page["images_with_alt"]:
            warnings.append(f"image alt text needs review: {page['route']}")
    for page in pages:
        if page["private"] and not page["noindex"]:
            warnings.append(f"private route may be indexable: {page['route']}")

    return {
        "framework": "next-app-router",
        "root": str(root),
        "pages": pages,
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
