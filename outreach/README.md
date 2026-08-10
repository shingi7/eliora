# EliOra local-first outreach engine

This is a small-volume, owner-controlled research and outreach operations tool for EliOra Tech Solutions LLC. It is intentionally separate from the Quarto marketing site. The public site never imports this package and the package never writes runtime state into `docs/`.

## What it does—and does not do

The tool plans bounded public-web discovery, retrieves approved public pages, records source evidence, separates observed signals from pain hypotheses, scores companies deterministically, drafts concise messages, and maintains a local audit/outbox/suppression record. It can later use OpenAI's Responses API for discovery, structured extraction, and quality review, and Namecheap Private Email SMTP/IMAP for owner-controlled sending.

It does not scrape LinkedIn or private networks, use purchased lists or email-finder services, guess addresses, probe mailboxes, bypass CAPTCHAs, handle PHI in a sales demo, auto-reply to people, track opens/clicks, or send while live mode is disabled. A model cannot override a deterministic compliance gate.

## Test with ChatGPT research before API billing

The owner can exercise the downstream research, scoring, dashboard, and draft workflow without automated OpenAI usage:

```bash
./outreachctl research prompt > /tmp/eliora-chatgpt-prompt.txt
./outreachctl research schema --output /tmp/eliora-research-schema.json

# After ChatGPT produces a strict prospects JSON bundle:
./outreachctl research validate ~/Downloads/prospects.json
./outreachctl research import ~/Downloads/prospects.json
# If an older import predates contact-independent draft persistence:
./outreachctl research reconcile-import IMPORT_ID ~/Downloads/prospects.json
# Recheck only contacts from one imported batch; this never sends:
./outreachctl research verify-import IMPORT_ID
./outreachctl scores recompute --origin external
./outreachctl scores show --origin external
./outreachctl dashboard
```

Manual imports send zero emails, remain subject to permission and provider policy, and do not complete the automated production-web doctor gate. They do not prove automated OpenAI API research works; that path can be commissioned later. Imported records remain private and separate from the public Quarto site.

Commercial prioritization is separate from dispatch compliance. `scores recompute` preserves the legacy score and adds deterministic Opportunity Fit, Reachability, project framing, and priority fields; it creates no drafts or outbox rows and sends nothing. The default lead order is Opportunity Fit, Reachability, signal freshness, and deterministic tie-breaker. Permission, provider policy, contact provenance, draft approval, live state, and send-window checks remain separate dispatch gates.

The modes are intentionally distinct:

```sh
./outreachctl demo
# DEMO / SYNTHETIC — offline fixtures and fake mail; never production data

./outreachctl run --dry-run --max-qualified 5
# REAL production web research and drafting; prospect sending is disabled

./outreachctl run --live
# The same production research pipeline, followed only by separately gated dispatch
```

Production research fails closed when the OpenAI key/provider is unavailable; it never falls back to the synthetic demo. A dry run writes production evidence, leads, and review drafts, but creates no prospect outbox message and records `prospect_messages_sent: 0`.

## Conservative operating principles

- US-only automatic outreach is the default.
- Contact data must be explicitly published on the candidate company's official registrable domain.
- Free/personal mailboxes and inappropriate role inboxes are rejected.
- Every observed signal has a URL, title, retrieval date, and excerpt. A hypothesis is labeled as an inference and points to supporting signal IDs.
- Every message has accurate From, To, Reply-To, Date, Message-ID, a business-outreach disclosure, physical postal address, and reply-based opt-out. The owner BCC is added only to the SMTP envelope, never as a visible `Bcc:` header.
- A reply, owner manual reply, bounce, opt-out, or not-interested response cancels future automation.
- One initial plus at most two follow-ups; defaults are 5 and 12 business days.
- The default daily hard ceiling is 10 prospect-directed messages and 20 total recipient deliveries including the owner BCC. Warm-up caps and weekday recipient windows are enforced.

This is an implementation of conservative controls, not legal advice. Have counsel review the final policy and sender/domain setup.

## 15-minute local installation

Python 3.11 or newer is required. From the repository root:

```sh
python3 -m venv outreach/.venv
source outreach/.venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e "outreach[dev]"
./outreachctl --help
```

Windows PowerShell equivalents:

```powershell
py -3.11 -m venv outreach\.venv
& outreach\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e "outreach[dev]"
.\outreachctl --help
```

Runtime paths use the operating system's private application-data/config/log locations. The repository is never a secrets store. Setup writes config with mode `0600` where supported.

## First setup

The normal setup uses EliOra's production defaults: `America/New_York`, research at `09:00`, send window `07:00`–`19:00`, five recommended initial messages, one recommended follow-up, and a hard prospect cap of ten. The model remains `gpt-5.4-mini`. A blank meeting link is valid and produces no call-to-action or placeholder.

Run:

```sh
./outreachctl setup
./outreachctl config show
```

Normal setup is concise and idempotent: it preserves saved values and only asks for the one-time private physical postal address when missing, an optional meeting link when not configured, the policy acknowledgement when needed, and a first-run save confirmation. The real postal address is stored only in the mode-0600 private config; it is intentionally absent from source, examples, documentation, and Quarto output. No password or API key is requested by setup. Use `./outreachctl setup --advanced` to edit every non-secret field, including sender copy, URLs, schedule, quotas, transport settings, targeting, and model choice. Invalid input is rejected before the existing config is replaced.

The OpenAI key can remain in the environment as `ELIORA_OPENAI_API_KEY`, or be stored without echoing it:

```sh
./outreachctl secrets set-openai-key
./outreachctl secrets status
```

`config show` reports effective non-secret values, private paths, masked identities, whether mailbox/OpenAI secrets exist in the OS credential store, live state, and scheduler state. It never prints the postal address or a secret. Sender identity is not inferred from old pages, backups, generated files, or Git history.

## Namecheap Private Email commissioning

The default transport is `mail.privateemail.com`: SMTP over implicit TLS on port 465 and IMAP over implicit TLS on port 993. STARTTLS on ports 587/143 can be selected in the private config when required. The mailbox username is the complete mailbox address. The password is accepted only by `secrets set-mail-password` and is stored in the operating system credential store; it is never written to YAML, SQLite, logs, exports, or process arguments.

Namecheap policy is fail-closed: cold prospects without an eligible permission basis can still be researched, scored, drafted, and exported, but are never auto-dispatched through this provider. Eligible bases are recorded per company, such as an owner-approved warm relationship, explicit inbound request, or contractual/transactional necessity.

Record an owner-auditable basis when one exists:

```sh
./outreachctl lead set-permission COMPANY_ID --basis existing_relationship --source "Owner CRM note 2026-08-09"
```

## Attaching a researched public contact

When a legitimate public business source identifies a contact for an existing
lead, attach it with the real source URL. This records provenance, leaves source
verification as `not_checked`, recomputes Reachability only, and does not change
permission or create send work:

```sh
./outreachctl lead add-contact COMPANY_ID \
  --email "person@company.com" \
  --name "Person Name" \
  --title "Revenue Operations" \
  --source-url "https://PUBLIC_SOURCE_URL" \
  --source-type reputable_news \
  --extraction-method visible_text \
  --draft-id DRAFT_ID
```

## Recording a manually sent prospect message

If an owner sends a prospect message outside EliOra, record the existing draft
without sending another message. The actual recipient and subject are required;
`--sent-at` is optional but should be supplied when the historical send time is
known. The confirmation can be skipped with `--yes`.

```sh
./outreachctl manual-send candidates
./outreachctl manual-send record DRAFT_ID \
  --recipient "person@example.com" \
  --subject "The exact subject that was sent" \
  --sent-at "2026-08-10T15:30:00-04:00"
```

This is record-only: it does not construct SMTP transport, enable live mode, or
create a second message. The row is idempotent and becomes active duplicate-send
protection. If the RFC Message-ID or Sent UID is not available, leave them null;
the bounded IMAP reconciliation checks only the Sent folder using recipient,
subject, and a recent time window:

```sh
./outreachctl manual-send reconcile --window-minutes 180
```

## Explicit one-draft send

An approved draft with a persisted, validated contact can be sent once by an
explicit owner command. This path does not enable live mode or grant future
permission for autonomous dispatch. It previews the complete message and asks
for confirmation unless `--yes` is supplied:

```sh
./outreachctl send-now DRAFT_ID
./outreachctl send-now DRAFT_ID --recipient "person@company.com" --yes
```

`--recipient`, when used, must match the persisted contact exactly. Contactless
drafts must first use `lead add-contact`; this avoids creating an untracked
recipient outside the existing contact and reply-history model. A sent or
uncertain draft is blocked from another attempt.

## Doctor, owner-only test, dry run, and live mode

Use this sequence:

```sh
./outreachctl setup
./outreachctl secrets set-mail-password
./outreachctl secrets set-openai-key  # optional; environment fallback is supported
./outreachctl auth private-email
./outreachctl doctor
./outreachctl send-test
./outreachctl run --dry-run --max-qualified 5
./outreachctl dashboard
./outreachctl live enable
./outreachctl schedule install
./outreachctl schedule status
```

`send-test` is owner-only and cannot be pointed at a prospect. It sends one explicitly confirmed owner test through SMTP and reconciles the exact RFC `Message-ID` in the IMAP Sent folder. The first activation also requires SMTP/IMAP authentication, verified mailbox identity, reply sync, the acknowledged provider policy, owner BCC, postal/disclosure/opt-out copy, a successful owner test, a successful production web-research dry run, healthy database, no uncertain sends, and the exact phrase `ENABLE ELIORA OUTREACH`. Live mode is off by default. The implementation and tests never send real prospect messages.

Rotate a mailbox password with `./outreachctl secrets set-mail-password`; remove it with `./outreachctl secrets delete-mail-password`. Re-run `./outreachctl auth private-email` for a guarded connection check. Inspect the dashboard Messages page and `doctor` output for uncertain deliveries, pause immediately with `./outreachctl pause`, disable live mode with `./outreachctl live disable`, and remove the OS scheduler with `./outreachctl schedule uninstall`.

The dashboard listens on `127.0.0.1:8765` by default. It shows evidence, score components, draft findings, outbox state, suppressions, runs, and masked settings. State-changing requests use a session-local CSRF token. It has no remote fonts, analytics, tracking pixels, or automatic response action.

## Scheduling and missed runs

Install the OS-native scheduler:

```sh
./outreachctl schedule install
./outreachctl schedule status
./outreachctl schedule uninstall
```

macOS uses a `RunAtLoad` LaunchAgent plus a one-hour interval. Linux uses a user systemd timer with `OnBootSec=5m`, `OnUnitActiveSec=1h`, and `Persistent=true`. Windows uses a current-user Task Scheduler task at login plus hourly repetition. Scheduler files contain absolute executable paths, not secrets.

Each invocation uses a lock and a unique local-date run key. If the laptop was asleep through the morning, one current business-day research cycle may run after wake; old missed days are not replayed. Research may happen outside the send window, but queued messages wait for the recipient window. A late-night wake never dumps a missed batch.

## Pause, suppression, and replies

Pause immediately with:

```sh
./outreachctl pause
./outreachctl resume
```

The same state is visible to the scheduler and dashboard. Suppress an address, domain, or company permanently:

```sh
./outreachctl suppress add "person@company.com" --scope email --reason "owner request"
./outreachctl suppress list
./outreachctl suppress remove SUPPRESSION_ID --reason "deliberate owner correction"
```

Reply synchronization only examines tracked threads. Explicit `unsubscribe`, `stop`, `remove me`, `no thanks`, not-interested language, hard bounces, any substantive human reply, and any owner-written manual reply stop future sequence messages. Out-of-office is delayed only when a return date is reliable; ambiguity pauses for review. The tool never auto-replies.

## Changing targeting and volume safely

Edit the private YAML—not `config.example.yml`—to change vertical weights, exclusions, fresh-signal age, cooldown, follow-up timing, caps, or score thresholds. Vertical weights must total 100. The recommended initial volume should remain below the hard ceiling. Keep an auto-send threshold of at least 82 unless the owner has a documented review reason; live activation refuses a hard daily prospect cap over 10 and requires a second explicit acknowledgement for any lower threshold policy.

Research quotas are bounded by default: 8 search queries, 30 raw candidates, 12 fully researched companies, 5 qualified drafts, 20 web-search calls/run, 30 analysis calls/run, 80 official-site requests/run, and 8 pages/company. Usage, request IDs, source URLs, tool calls, and token counts are recorded per run. Model costs are estimates only and should be configured from current provider pricing rather than treated as permanent facts.

## Domain reputation checklist

Use the actual sender provider's SPF, DKIM, and DMARC guidance. Confirm the authenticated From and Reply-To identity, valid reverse/account configuration where applicable, a conservative ramp, mailbox monitoring, and a real physical postal address. DNS checks in `doctor` are advisory; an SPF/DKIM/DMARC record alone does not prove deliverability.

## Troubleshooting and recovery

- `outreachctl doctor` reports missing Python version, config, database, mailbox secret, transport policy, or sender checks without showing secrets.
- Re-run `auth private-email` after changing the mailbox password; never copy a password into Git or config.
- Network or provider failures are retryable research states; no partial unvalidated send is created.
- An uncertain outbox message is reconciled by searching Sent for its exact stored RFC 5322 Message-ID before any retry.
- SQLite is WAL-mode and uses explicit schema creation. Back up the private database while the process is paused; use `export --format csv --output PATH` for a portable lead export.
- Purge cached public-page text with `./outreachctl privacy purge-cache --older-than 90`.

## Cloud migration notes

The core interfaces separate SQLite from providers, so a later deployment can use Docker, environment variables/secret manager, PostgreSQL, a managed scheduler/worker, and a managed email provider. Preserve idempotency keys, Message-IDs, suppression transactions, and audit records. A public unsubscribe endpoint should be added only with a deliberate security/legal design; localhost mailto reply opt-out is not RFC 8058 one-click HTTPS. Do not move private cache or mailbox credentials into a public web build.

## Offline demo and development checks

The demo uses a synthetic `.example` company and fake research/mail providers; it requires no network, API key, mailbox, or browser session. Offline validation uses a separate production-shaped fake provider and never claims that real web commissioning has run:

```sh
./outreachctl demo
cd outreach
pytest
ruff check .
ruff format --check .
mypy src
```

The demo exercises synthetic evidence, deterministic scoring, guarded drafting, fake outbox send, reply classification, and permanent suppression. No implementation validation sends a real prospect email.
