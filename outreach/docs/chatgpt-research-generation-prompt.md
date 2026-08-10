# ChatGPT research-generation prompt

Use the following prompt with ChatGPT web research. Replace `N` with the requested company limit and require the current schema from `./outreachctl research schema`.

```text
You are preparing an EliOra external research bundle. Research up to N real US companies relevant to EliOra's canonical services using current public web research.

Output JSON only, matching schema_version "1.0" and bundle_type "eliora_external_research". Use the exact schema emitted by `outreachctl research schema`; do not use Markdown fences or commentary.

Prioritize current operating or buying signals from official company, careers, government, regulator, reputable news, or trade sources. Preserve source URLs and short excerpts. Every observed fact must reference evidence IDs from the same company. Keep pain hypotheses tentative and separately linked to facts. Store a concise rationale only; never include hidden chain-of-thought.

Find only explicitly published official-domain business contacts. Never guess an email, scrape LinkedIn, use a broker or purchased list, probe SMTP, or use a personal mailbox. Set every contact permission_basis to "unknown" unless the owner supplied legitimate evidence separately.

Never fabricate dates, employee counts, metrics, company facts, or publication dates. Use null when unknown. Do not include auto_send, dispatch_eligible, provider_allowed, suppression, live state, or a final score. Use only canonical service_key values and their canonical names/URLs.
```
