# EliOra flagship redesign notes

## Concept and tokens

The site is built around “Signal → Decision”: raw inputs enter a disciplined system, noise resolves through mapped paths, and the visitor is guided toward a useful next move. The hero instrument is local inline SVG with CSS-led motion and a fine-pointer light field; the Work / Lab page uses the existing football prototypes as honest internal R&D proof.

The main design tokens live at the top of `styles.css`: deep ink `#05080D`, dark surface `#0B121B`, raised surface `#111C28`, primary text `#F4F7F8`, muted text `#A8B5C2`, electric cyan `#61E5FF`, cyan action `#20BADA`, and restrained signal-lime `#C8FF68`. System font stacks keep the site local and fast; the monospace stack is reserved for instrumentation and labels.

## Page map

- `/` — positioning, Reporting Automation Sprint, capabilities, R&D proof, approach, founders preview
- `/services.html` — featured sprint, broader service modules, operating principles
- `/work.html` — Business Systems Lab, research context, methodology, and all seven public lab routes
- `/about.html` — practice thesis, factual founder bios, operating principles
- `/contact.html` — progressive-enhanced Formspree inquiry form
- `/site/reporting-control-room.html`, `/site/revenue-margin-forecast.html`, `/site/pipeline-intelligence.html`, `/site/support-operations.html` — deterministic Business Systems Lab prototypes
- `/site/executive-demo.html`, `/site/player-st.html`, `/site/team-prototype.html` — football R&amp;D routes with preserved analytics logic and data contracts

## Shared architecture

`includes/site-head.html` supplies global metadata and Organization / ProfessionalService JSON-LD. `includes/site-header.html` and `includes/site-footer.html` are Quarto HTML includes used by `_quarto.yml`, so navigation, skip link, mobile menu, footer, and the shared script are not repeated in page sources. Each page supplies `data-page` for active navigation and keeps content inside Quarto’s single generated main landmark.

`script.js` contains only navigation, sticky-header state, progressive section reveals, the hero pointer enhancement, the contact-form fetch enhancement, and the dynamic year. CSS uses a `.js` enhancement class and removes nonessential movement under `prefers-reduced-motion: reduce`.

Standalone lab routes use `site/lab-shell.css` and `site/lab-shell.js` for the persistent header, mobile menu, footer conventions, focus states, reduced motion, and dark visual system. Business demos add `site/business-demo.css`, `site/demo-utils.js`, and page-specific JavaScript. New business routes use no external chart library; SVG charts are paired with table equivalents. Dialogs, copy, export, filters, and review states are local-only. The football pages retain Plotly because it is part of the existing prototype logic, but use EliOra chart colors and dark backgrounds.

## Assets, SEO, and domain

The original `logo.png`, `tev_headshot.png`, and `shingi_headshot.png` remain untouched. Local `sips` derivatives in `assets/optimized/` reduce display sizes; `assets/favicon.png` is a clean crop of the existing circuitry mark and `assets/social-preview.png` is a padded derivative of the existing logo identity. Explicit image dimensions, loading hints, `decoding`, local font stacks, and no marketing iframes keep the primary site lightweight.

`_quarto.yml` sets the production site URL, page descriptions, Open Graph/Twitter card support, favicon, disabled Quarto search, and copies `CNAME`, `robots.txt`, and `sitemap.xml` into `docs/`. `CNAME` contains exactly `elioratechsolutions.com`.

## Build and verification commands

```text
quarto render
git diff --check
python3 scripts/check_site.py
```

Chrome headless is available in the environment for static screenshots and DOM inspection. Lighthouse was not run unless explicitly invoked; no performance score is claimed here. The current football prototype pages retain their own Plotly dependency because it is part of those existing interactive proof routes; the four new business pages have no external chart library. The primary marketing pages have no Three.js, Vanta, GSAP, font CDN, or eager iframe dependency.

## Synthetic-data policy

Business Systems Lab routes use fixed local arrays and scenario values so every view is repeatable. They visibly say synthetic, avoid live-system claims, and keep copy/export/review actions in the browser. The forecast route includes a no-financial-advice disclosure; the support route drafts guidance for human review and intentionally has no Send action.

## Future content

The live site intentionally does not include client case studies, testimonials, client logos, performance statistics, prices, or response-time promises. Future client-approved case studies can be added to Work / Lab when the underlying claims and permissions are available.
