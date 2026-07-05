---
name: webdev
description: When the user wants to build, design, or create a website, landing page, web app UI, or any web presence for any business, product, or niche -- run this skill
---

Build a high-converting, production-ready website for the following:

**Project:** $ARGUMENTS

Work through every phase below without stopping. Produce real, shippable code — not mockups, not placeholders.

---

## PHASE 1 — DEEP RESEARCH (run all 4 tracks in parallel)

Launch 4 independent research agents simultaneously. Each agent uses WebSearch + WebFetch. Do NOT summarize from memory — fetch live pages and extract real data.

### Track A — Market & Audience
- Who is the exact target customer? Demographics, pain points, language they use, jobs to be done.
- What does this market pay for, fear, and aspire to?
- What search intent brings them to this type of site? (informational / commercial / transactional)
- What are the top 3-5 direct competitors? Fetch their homepages and note: headline, CTA, proof elements, offer structure, pricing display.

### Track B — Conversion Research
- Fetch and read at least 5 sources on high-converting landing pages for this industry/type (CXL, Nielsen Norman, Unbounce blog, case studies)
- What above-the-fold formula converts best for this audience?
- Ideal CTA copy patterns for this vertical
- What trust signals matter most (reviews, certifications, client logos, guarantees, numbers)?
- What objections kill conversions and how do top sites pre-empt them?
- What is the optimal page length, scroll depth, and CTA frequency for this offer?
- Email capture vs direct-sale vs book-a-call — which funnel fits?

### Track C — Design & UI Trends
- Fetch Dribbble, Awwwards, Behance, and/or Mobbin for the closest design category
- What visual style dominates high-performing sites in this niche right now (minimal, bold editorial, dark luxury, clean SaaS, warm human, etc.)?
- Current typography trends: which font pairings are winning?
- Color psychology: what palette triggers the right emotion for this audience?
- Animation and micro-interaction patterns that increase engagement without hurting performance
- Mobile UX patterns: how do top converters handle navigation, CTAs, and forms on mobile?

### Track D — Technical & SEO Baseline
- What Core Web Vitals thresholds do top competitors hit?
- What structured data / schema types are relevant?
- What meta and OG patterns do top-ranking pages in this vertical use?
- What performance budget should we target (LCP, CLS, INP)?
- Any compliance requirements (GDPR cookie banner, accessibility WCAG 2.1 AA, etc.)?

---

## PHASE 2 — SYNTHESIS & STRATEGY

After all 4 tracks complete, synthesize into a single strategy document (write it as a comment block at the top of the HTML file, or as a separate `_STRATEGY.md`). Include:

1. **One-sentence value proposition** — what the site promises in 8 words or fewer
2. **Primary CTA** — the single most important action (book a call / sign up / get quote / buy)
3. **Page architecture** — ordered list of sections with their job (e.g. "Hero: state the promise and primary CTA", "Social proof: kill the #1 objection")
4. **Conversion hypothesis** — what specific combination of elements should drive the highest conversion and why
5. **Color palette** — primary, secondary, accent, background, text (hex codes)
6. **Typography** — headline font + body font + size scale (use Google Fonts or system fonts only)
7. **Tone of voice** — 3 adjectives; 2 things to avoid

---

## PHASE 3 — BUILD THE WEBSITE

Build a single-file `index.html` (or a small multi-file project if scope warrants) that is fully shippable. Use:
- **Vanilla HTML + CSS + minimal JS** unless the project specifically calls for a framework
- Google Fonts via `<link>` in `<head>` (no CDN JS libraries unless essential)
- No placeholder Lorem Ipsum — every word of copy is real, researched, conversion-optimized
- No placeholder images — use CSS gradients, SVG illustrations, or `https://images.unsplash.com` for hero imagery with descriptive alt text

### Required sections (adapt to fit the project):

**Hero**
- Headline: outcome-focused, specific, speaks to the #1 desire
- Subheadline: removes the #1 objection in one sentence
- Primary CTA button (above the fold, high-contrast, action verb)
- Supporting trust micro-copy beneath CTA ("No credit card required" / "500+ clients" / etc.)
- Hero visual: CSS illustration, gradient, or real image

**Social Proof Bar**
- Logos, star ratings, or a single standout number (e.g. "Trusted by 1,200+ nurses in 18 countries")
- Immediately below hero — this is where doubt first spikes

**Problem / Empathy Section**
- Name the pain exactly as the customer feels it (use the language from Track A research)
- 2-3 short bullets or a brief paragraph — do NOT over-explain

**Solution / How It Works**
- 3-step process or feature grid
- Each point: what it is + what it does for them (benefit, not feature)
- Icon or simple illustration per point (SVG inline or CSS shape)

**Proof / Results Section**
- 2-3 testimonials with name, photo placeholder (CSS avatar), and a specific outcome ("Got my Germany visa in 6 weeks")
- Or: case study numbers, before/after, client results

**Offer / Pricing Section** (if applicable)
- Clear offer name, what's included, price or "starting from"
- One recommended plan highlighted
- Guarantee or risk reversal statement

**FAQ**
- 4-6 questions addressing the real objections found in Track B research
- Accordion or simple Q&A (no JS accordion unless you implement it)

**Final CTA Section**
- Repeat the primary CTA with urgency or scarcity framing
- One last piece of social proof or trust signal

**Footer**
- Logo, tagline, nav links, contact, social links, legal links
- Copyright line

---

## PHASE 4 — CONVERSION ENGINEERING

After the sections are built, make these specific optimizations:

**Copy**
- Headline uses a power word (the research found what works — use it)
- Every CTA button starts with a verb ("Get", "Start", "Book", "Claim", "See")
- Objection-handling copy is placed immediately BEFORE the CTA it supports
- Numbers are specific ("47 clients" not "many clients", "6 weeks" not "fast")

**Visual hierarchy**
- One thing on screen at a time draws the eye — no competing focal points
- CTA buttons: high-contrast fill color, 48px+ height, generous padding, border-radius that fits the brand style
- Whitespace is generous — sections breathe, nothing feels crammed

**Performance**
- All CSS in `<style>` block (or a single linked stylesheet) — no render-blocking resources
- Images have `loading="lazy"` except the hero (which gets `fetchpriority="high"`)
- `<meta name="viewport" content="width=device-width, initial-scale=1">`
- Semantic HTML: `<main>`, `<section>`, `<nav>`, `<article>`, `<footer>` used correctly
- All interactive elements keyboard-accessible

**SEO**
- `<title>` tag: primary keyword + brand name, under 60 chars
- Meta description: benefit-led, under 155 chars, includes CTA
- H1 matches or closely mirrors the hero headline
- H2s on each major section contain secondary keywords naturally
- OG tags: `og:title`, `og:description`, `og:image`, `og:url`
- Schema.org JSON-LD in `<head>`: at minimum `Organization` or `LocalBusiness`; add `FAQPage` schema for the FAQ section

**Mobile**
- Test every section at 375px width — nothing overflows, no horizontal scroll
- Touch targets 44px minimum
- Font size never below 16px on body text
- CTA button full-width on mobile

---

## PHASE 5 — SELF-REVIEW (before declaring done)

Run this checklist against the finished build. Fix anything that fails before reporting complete.

**Conversion**
- [ ] Value proposition is clear within 3 seconds of landing
- [ ] Primary CTA appears above the fold without scrolling (on desktop and mobile)
- [ ] At least 3 trust signals are visible before the first CTA
- [ ] Every section has exactly one job and does it
- [ ] No Lorem Ipsum, no placeholder copy anywhere
- [ ] All CTAs use action verbs and are visually dominant

**Design**
- [ ] Color palette is consistent throughout (exactly the hex codes chosen in Phase 2)
- [ ] Font pairing is consistent — no more than 2 typefaces
- [ ] Spacing is consistent — sections use the same vertical rhythm
- [ ] Mobile layout looks polished at 375px (check every section mentally)
- [ ] No walls of text — longest paragraph is 3 sentences max

**Technical**
- [ ] HTML validates (no unclosed tags, no missing alt attributes)
- [ ] No external JS CDN dependencies that block render
- [ ] Schema JSON-LD is present and correct
- [ ] OG tags are complete
- [ ] `<title>` and meta description are filled with real content

**Content**
- [ ] All copy is specific and outcome-focused (no vague filler)
- [ ] FAQ answers the objections found in research, not generic questions
- [ ] Testimonials sound human, not corporate ("I got my visa in 6 weeks!" not "Excellent service")

---

## OUTPUT

Deliver:
1. The complete `index.html` (and any supporting files) — fully shippable, open in a browser and it works
2. A brief summary (5-8 bullets) of the key conversion decisions made and why
3. One specific A/B test hypothesis to run first after launch (what to test, what to measure, what winning looks like)
