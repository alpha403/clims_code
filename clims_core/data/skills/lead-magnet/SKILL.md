---
name: lead-magnet
description: When the user wants to create a lead magnet, freebie, opt-in gift, guide, checklist, swipe file, template, or any free resource to grow an email list or generate leads for any brand -- run this skill
---

Research, write, and design a complete lead magnet for the following:

**Brief:** $ARGUMENTS

If the brief is missing details, ask for:
- **Brand:** name, colors (hex), logo path (if any), niche
- **Target audience:** who is this for?
- **Offer context:** what are they opting in to get? What page/ad drives them here?
- **Lead magnet type:** guide / checklist / swipe file / template / quiz / mini-course / calculator / report (or let research decide)
- **Output format:** HTML (rendered to PDF or hosted page) or styled document

---

## PHASE 1 — RESEARCH (run all 3 tracks in parallel)

### Track A — Audience Pain & Desire Mapping
- What is the single biggest problem this audience wants solved RIGHT NOW?
- What transformation do they want — what does "after" look like for them?
- What have they already tried and failed? What makes them skeptical?
- What is the ONE quick win they could get in under 10 minutes that would make them trust this brand immediately?
- Search Reddit, Quora, Facebook groups, and YouTube comments in this niche — extract exact phrases they use

### Track B — Lead Magnet Competitive Research
- Fetch 5-7 lead magnets from top brands in this niche (search "[niche] free guide", "[niche] checklist", "[niche] template")
- What format dominates: PDF guide, checklist, video, email course, quiz?
- What titles convert best? (look at opt-in page headlines and ad copy)
- What do they promise on the cover vs what they actually deliver?
- What are the gaps — what would make our lead magnet 10x more useful than the competition?

### Track C — Conversion & Opt-in Research
- What opt-in page headline formulas convert best for this type of lead magnet?
- What is the ideal lead magnet length for maximum perceived value without overwhelm? (checklists: 1 page; guides: 5-12 pages; templates: 1-3 pages)
- What specificity level converts best? (specific beats vague: "7 Steps to Get a German Visa in 90 Days" beats "The Germany Immigration Guide")
- What is the #1 reason people DON'T opt in to lead magnets in this niche?

---

## PHASE 2 — STRATEGY

Define before writing:
- **Title:** specific, outcome-focused, includes a number or timeframe if possible
- **Subtitle:** expands the promise, addresses the #1 objection
- **Core promise:** one sentence — what will they know/have/be able to do after consuming this?
- **Format chosen + why:** based on research, what format delivers the highest perceived value for this audience?
- **Quick win:** what is the single most actionable thing they can implement immediately?

---

## PHASE 3 — WRITE THE CONTENT

Write every word of the lead magnet. No placeholder sections. Real, researched, actionable content throughout.

### Structure (adapt to format):

**Cover:**
- Title + subtitle
- Brand name + logo
- "A [Brand] Resource" or similar
- One-line promise ("Read this and you'll know exactly how to X")

**Introduction (1 page max):**
- Who this is for (and who it's NOT for — increases trust)
- What they'll get from it
- One sentence on why the brand is qualified to write this

**Core Content:**
- Organised into clear sections with headings
- Each section delivers ONE concept, step, or tool
- Real examples, real numbers, real outcomes — no vague generalities
- Callout boxes for key insights, warnings, or pro tips
- Visuals described in HTML/CSS (charts, icons, highlighted boxes) or noted for the designer

**Quick-Win Section:**
- The single most actionable item — something they can do TODAY
- Formatted as a mini step-by-step (3-5 steps max)

**Next Step / CTA:**
- Bridge to the offer: "If you want help implementing this..."
- One CTA: book a call / join the community / buy the product
- Make it feel like a natural next step, not a hard sell

---

## PHASE 4 — DESIGN (HTML output)

Build a single `lead_magnet_{rid}.html` file that renders as a polished document:
- Brand colors and fonts from the brief
- Clean, readable layout: max 700px content width, generous margins
- Section dividers, callout boxes, numbered lists styled with CSS
- Cover page as the first screen/section
- Print-friendly (`@media print` CSS so it saves to PDF cleanly)
- No external dependencies — all CSS inline or in `<style>` block

---

## PHASE 5 — OPT-IN PAGE COPY

After the lead magnet content, write the opt-in page copy (to be used in the `webdev` skill or pasted into an existing page):
- **Headline:** outcome-focused, specific, under 10 words
- **Subheadline:** addresses the #1 objection or expands the promise
- **3 bullet points:** what they'll discover/get (benefit, not feature)
- **CTA button text:** action verb + outcome ("Get the Free Guide", "Send Me the Checklist")
- **Trust micro-copy:** under the button ("Free. No spam. Unsubscribe anytime.")

---

## SELF-CHECK (before delivering)

- [ ] Title is specific and includes an outcome or number
- [ ] Every section has real, actionable content — no filler or padding
- [ ] Quick win is genuinely doable in under 10 minutes
- [ ] CTA feels like a natural next step, not a pitch
- [ ] Design is clean, on-brand, and readable on screen and when printed to PDF
- [ ] Opt-in page copy promises exactly what the lead magnet delivers (no bait and switch)
- [ ] No placeholder copy anywhere — fully production-ready
