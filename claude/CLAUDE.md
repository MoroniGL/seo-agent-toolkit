# SEO Agent Toolkit for Claude Code

When a request concerns SEO for a coded website, use the shared audit script first:

```bash
python3 scripts/seo_audit.py --root . --format text
```

Follow `skills/seo-agent/SKILL.md` for the audit, plan and fix modes. Claude Code should treat `audit` as read-only and require an explicit user request before applying changes. Use the project's own test, lint, typecheck and build commands after any fix.
