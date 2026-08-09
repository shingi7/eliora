# EliOra flagship redesign notes

## Concept and tokens

The site is built around “Signal → Decision”: raw inputs enter a disciplined system, noise resolves through mapped paths, and the visitor is guided toward a useful next move. The hero instrument is local inline SVG with CSS-led motion and a fine-pointer light field; the Work / Lab page uses the existing football prototypes as honest internal R&D proof.

The main design tokens live at the top of `styles.css`: deep ink `#05080D`, dark surface `#0B121B`, raised surface `#111C28`, primary text `#F4F7F8`, muted text `#A8B5C2`, electric cyan `#61E5FF`, cyan action `#20BADA`, and restrained signal-lime `#C8FF68`. System font stacks keep the site local and fast; the monospace stack is reserved for instrumentation and labels.

## Page map

- `/` — positioning, Reporting Automation Sprint, capabilities, R&D proof, approach, founders preview
- `/services.html` — featured sprint, broader service modules, operating principles
- `/work.html` — Football Decision Intelligence Lab and all three live prototypes
- `/about.html` — practice thesis, factual founder bios, operating principles
- `/contact.html` — progressive-enhanced Formspree inquiry form
- `/site/executive-demo.html`, `/site/player-st.html`, `/site/team-prototype.html` — preserved interactive proof routes

## Shared architecture

`includes/site-head.html` supplies global metadata and Organization / ProfessionalService JSON-LD. `includes/site-header.html` and `includes/site-footer.html` are Quarto HTML includes used by `_quarto.yml`, so navigation, skip link, mobile menu, footer, and the shared script are not repeated in page sources. Each page supplies `data-page` for active navigation and keeps content inside Quarto’s single generated main landmark.

`script.js` contains only navigation, sticky-header state, progressive section reveals, the hero pointer enhancement, the contact-form fetch enhancement, and the dynamic year. CSS uses a `.js` enhancement class and removes nonessential movement under `prefers-reduced-motion: reduce`.

## Assets, SEO, and domain

The original `logo.png`, `tev_headshot.png`, and `shingi_headshot.png` remain untouched. Local `sips` derivatives in `assets/optimized/` reduce display sizes; `assets/favicon.png` is a clean crop of the existing circuitry mark and `assets/social-preview.png` is a padded derivative of the existing logo identity. Explicit image dimensions, loading hints, `decoding`, local font stacks, and no marketing iframes keep the primary site lightweight.

`_quarto.yml` sets the production site URL, page descriptions, Open Graph/Twitter card support, favicon, disabled Quarto search, and copies `CNAME`, `robots.txt`, and `sitemap.xml` into `docs/`. `CNAME` contains exactly `elioratechsolutions.com`.

## Build and verification commands

```text
quarto render
git diff --check
python3 scripts/check_site.py
```

Chrome headless is available in the environment for static screenshots and DOM inspection. Lighthouse was not run unless explicitly invoked; no performance score is claimed here. The current prototype pages retain their own Plotly dependency because it is part of those existing interactive proof routes; the primary marketing pages have no Three.js, Vanta, GSAP, font CDN, or eager iframe dependency.

## Future content

The live site intentionally does not include client case studies, testimonials, client logos, performance statistics, prices, or response-time promises. Future client-approved case studies can be added to Work / Lab when the underlying claims and permissions are available.
