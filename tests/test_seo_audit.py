import tempfile
import unittest
from pathlib import Path

from scripts.seo_audit import audit


class SeoAuditTests(unittest.TestCase):
    def test_excludes_private_routes_from_public_page_count(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "src/app/painel").mkdir(parents=True)
            (root / "src/app/about").mkdir(parents=True)
            (root / "src/app/painel/page.tsx").write_text("export default function Page() { return null }", encoding="utf-8")
            (root / "src/app/about/page.tsx").write_text("export const metadata = {}; export default function Page() { return null }", encoding="utf-8")

            result = audit(root)

        self.assertEqual(result["summary"]["total_pages"], 2)
        self.assertEqual(result["summary"]["public_pages"], 1)
        self.assertIn("private route may be indexable: /painel", result["warnings"])

    def test_inherits_noindex_from_private_layout(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            panel = root / "src/app/painel"
            panel.mkdir(parents=True)
            (panel / "layout.tsx").write_text("export const metadata = { robots: { index: false, follow: false } };", encoding="utf-8")
            (panel / "page.tsx").write_text("export default function Page() { return null }", encoding="utf-8")

            result = audit(root)

        self.assertNotIn("private route may be indexable: /painel", result["warnings"])

    def test_reports_broken_internal_links_and_orphan_public_routes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "src/app").mkdir(parents=True)
            (root / "src/app/about").mkdir()
            (root / "src/app/orphan").mkdir()
            (root / "src/app/page.tsx").write_text(
                '<a href="/about">About</a><a href="/missing">Missing</a><a href="https://example.com">External</a>',
                encoding="utf-8",
            )
            (root / "src/app/about/page.tsx").write_text("export const metadata = {};", encoding="utf-8")
            (root / "src/app/orphan/page.tsx").write_text("export const metadata = {};", encoding="utf-8")

            result = audit(root)

        self.assertEqual(result["broken_internal_links"], [{"source": "/", "target": "/missing"}])
        self.assertEqual(result["orphan_public_routes"], ["/orphan"])

    def test_reports_metadata_lengths_and_multiple_h1_headings(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            page_dir = root / "src/app/about"
            page_dir.mkdir(parents=True)
            (page_dir / "page.tsx").write_text(
                'export const metadata = { title: "Too short", description: "Too short" };'
                '<h1>About</h1><h1>Another heading</h1>',
                encoding="utf-8",
            )

            result = audit(root)

        page = result["pages"][0]
        self.assertEqual(page["title_length"], 9)
        self.assertEqual(page["description_length"], 9)
        self.assertEqual(page["h1_count"], 2)
        self.assertIn("title too short: /about", result["warnings"])
        self.assertIn("description too short: /about", result["warnings"])
        self.assertIn("expected one H1, found 2: /about", result["warnings"])


if __name__ == "__main__":
    unittest.main()
