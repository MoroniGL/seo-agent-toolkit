---
name: seo-agent
description: Audit and improve technical SEO in code-based websites, especially Next.js, with safe reports for metadata, canonicals, robots, sitemaps, structured data, social previews, accessibility and internal links.
metadata:
  short-description: Audit and improve SEO in code-based websites
---

# SEO Agent Toolkit

Use this skill when a user asks to improve SEO, replicate an SEO plugin's workflow in a coded website, or audit whether public pages are search-engine ready.

## Operating modes

- `audit`: inspect first and produce findings. Do not edit, deploy, submit forms, or change analytics/search-console settings.
- `plan`: turn findings into a prioritized change list with affected files and acceptance criteria.
- `fix`: only after the user explicitly authorizes implementation. Make the smallest safe changes, preserve business claims and pricing, and run the project's checks.

Start with `python3 scripts/seo_audit.py --root . --format text`. If the project is not Next.js, identify its framework before selecting an adapter.

## Non-negotiable safety

- Never invent reviews, ratings, locations, prices, certifications, opening hours, or service claims.
- Never index private areas, accounts, admin/panel routes, tokenized customer links, APIs, or test pages.
- Never expose secrets, personal data, access tokens, or credentials in reports or patches.
- Treat canonical URLs, redirects, robots rules, and structured data as production-impacting changes.
- Separate observed facts from recommendations and unresolved owner decisions.

## Audit checklist

Review the script output and then inspect the relevant source:

1. Site origin, canonical URL, title templates and descriptions.
2. Open Graph/Twitter metadata and social image dimensions/alt text.
3. Sitemap coverage and exclusion of private/API routes.
4. Robots rules, especially accidental admin exposure and conflicting allow/disallow rules.
5. JSON-LD validity and consistency with visible content: LocalBusiness, Service, FAQPage, Article, BreadcrumbList.
6. One unique H1, useful headings, image alt text and link text.
7. Duplicate metadata, missing metadata, broken internal links and orphan public routes.
8. Redirect/404 behavior and page indexing intent.

The link detector should be treated as conservative: static links can be verified directly, while dynamic navigation must be reported as limited rather than guessed.

When literal metadata is available, review title length (roughly 30–60 characters), description length (roughly 70–160 characters), and multiple H1 headings. Treat these as review signals, not absolute ranking rules, and never rewrite copy without the owner's approval.

For JSON-LD, validate literal script blocks only. Collect their `@type` values and flag missing `@context`, missing `@type`, or invalid JSON. Skip dynamic React/JavaScript expressions rather than guessing their runtime output.

## Framework guidance

For Next.js App Router, prefer `Metadata` exports, `metadataBase`, `app/robots.ts`, `app/sitemap.ts`, and server-rendered JSON-LD. Keep a single site-origin helper. Use nested layouts for metadata on client pages rather than exporting metadata from a client component.

For other frameworks, use their native metadata and routing primitives. Do not add a dependency merely to imitate a WordPress plugin.

## Fix workflow

Before editing, present the findings and scope. During `fix`:

- add regression tests for each behavior changed;
- use existing configuration and content sources;
- update shared helpers before duplicating page-level values;
- keep private routes `noindex, nofollow` and out of the sitemap;
- run the repository's lint, typecheck, tests and production build;
- report files changed, evidence, unresolved SEO decisions and rollback notes.

The toolkit is an independent implementation inspired by common technical SEO workflows. It is not affiliated with or copied from AIOSEO.
