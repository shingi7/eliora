# External research import

The Research Import Bridge lets an owner validate research prepared manually in ChatGPT before spending on automated OpenAI research. It uses the same EliOra company, evidence, signal, hypothesis, contact, score, draft, suppression, and dashboard models.

Imported records use `data_origin=external_research`, `run_mode=manual_import`, and `research_provider=chatgpt_manual`. They are real prospect research, not synthetic demo data. The automated production-web doctor gate remains independent and is not completed by an import.

## Commands

```bash
./outreachctl research schema
./outreachctl research schema --output /tmp/eliora-research-schema.json
./outreachctl research template --output /tmp/eliora-template.json
./outreachctl research prompt --max-companies 5
./outreachctl research validate prospects.json
./outreachctl research import prospects.json
./outreachctl research reconcile-import IMPORT_ID prospects.json
./outreachctl research verify-import IMPORT_ID
./outreachctl scores recompute --origin external
./outreachctl scores show --origin external
./outreachctl dashboard
```

`research validate` is read-only. `research import` previews the bundle, asks for confirmation unless `--yes` is supplied, and commits one atomic transaction. It never creates an outbox row or sends a prospect message. `--verify-sources` opts into the hardened public-page crawler; unreachable or robots-blocked pages remain review-only.

`research reconcile-import` requires the same bundle hash as an existing import and only materializes missing research drafts; it never creates a second import record or duplicates normalized company/evidence rows. `research verify-import` rechecks only contacts belonging to the selected import, records checked time/status/reason, and never changes permission basis or creates outbox rows. Both commands are safe to retry.

## Bundle contract

The current bundle is `schema_version: "1.0"` and `bundle_type: "eliora_external_research"`. The machine-readable contract is emitted by `research schema`. A bundle contains timezone-aware `generated_at`, source/method metadata, US research scope, and one or more companies.

Each company requires a real official domain and website, vertical, location, discovery signal, evidence, and observed facts. Evidence IDs are company-scoped and every factual claim must reference evidence. Evidence uses HTTP(S) URLs, short excerpts, source tier/type, retrieval time, and optional publication dates. `.example`, `.invalid`, `.test`, localhost, private IP, file, social, directory, and broker URLs are rejected for real imports.

Pain hypotheses are separate from facts and must reference facts. Definitive language is warned. Service keys must be in EliOra's canonical service registry; arbitrary service names and routes are not accepted.

Contacts require a published official-domain source, syntactically valid business email, domain relationship, approved extraction method, and `permission_basis: "unknown"`. Personal mailboxes, mismatched domains, guessed addresses, inappropriate inboxes, and missing provenance are rejected. MX checks are never used to probe recipients; optional local source verification only records whether the public source visibly contains the address.

Imported scores are ignored. EliOra recomputes deterministic scoring and centralized eligibility. Unknown permission, external origin, missing provenance, suppression, and draft warnings remain blocking conditions. Imported JSON cannot set `auto_send`, `dispatch_eligible`, `provider_allowed`, suppression, live state, or a final score.

The current local commercial score version uses Opportunity Fit (pain specificity 20, service match 20, trigger strength 15, small-project suitability 20, commercial buyability 15, evidence confidence 10) and Reachability (buyer persona clarity 30, appropriate business contact 30, contact provenance/verification 25, channel relevance 15). A/B/C/D grades use 85/70/50 thresholds. Missing contacts, permission basis, and provider policy are not Opportunity Fit inputs; Reachability describes actionability only and never authorizes sending. The legacy score remains available in lead detail, CLI output, and exports.

Drafts are checked by existing deterministic guardrails. The private configured disclosure, postal address, and opt-out footer are appended by EliOra; imported text does not replace footer configuration. A content-valid research draft is stored even when its contact is missing or unverified. Missing contact, unknown permission, and provider policy remain separate send-readiness gates; no research draft is ever queued automatically.

Imports are identified by a canonical bundle SHA-256 hash. Reimporting the exact bundle returns `already_imported`; existing evidence is deduplicated by company and canonical URL, while genuinely new evidence/signals are retained. Raw bundles are not copied into the repository or public site; the private audit record stores metadata, counts, warnings, and hash only.

## Privacy and commissioning

Do not include PHI, protected-trait inferences, private home addresses, breach data, or personal dossiers. The dashboard escapes imported fields and only renders safe HTTP(S) links. External research appears under the External Research filter and in the Imports page. It does not enable live mode, install a scheduler, or prove automated OpenAI research works.
