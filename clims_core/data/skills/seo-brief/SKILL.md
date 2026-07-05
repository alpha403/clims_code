---
name: seo-brief
description: When the user wants an SEO content brief, keyword research, blog post outline, SEO strategy, or wants to rank for a keyword or topic on Google -- run this skill
---

Research and produce a complete SEO content brief for the following:

**Brief:** $ARGUMENTS

If the brief is missing details, ask for:
- **Brand / website:** URL and niche
- **Topic or keyword:** what do we want to rank for?
- **Target audience:** who searches for this?
- **Goal:** rank for organic traffic / support a landing page / build topical authority / answer a specific query
- **Content type:** blog post / landing page / pillar page / FAQ / comparison page

---

## PHASE 1 — KEYWORD RESEARCH (run all 3 tracks in parallel)

### Track A — Primary & Secondary Keyword Research
- Search Google for the seed topic. Note: featured snippet, people also ask, related searches, autocomplete
- Identify the primary keyword (highest intent, most specific, realistic to rank for)
- Identify 5-10 secondary / LSI keywords (variants, related terms, subtopics — use in H2/H3s and body)
- Identify 3-5 long-tail keywords (questions, "how to", "best", "vs" — use as FAQs or subheadings)
- Note the estimated search volume and difficulty level for the primary keyword (low: <30 DA pages ranking; medium: 30-60 DA pages; high: 60+ DA pages)

### Track B — SERP Analysis
- Fetch and analyse the top 10 Google results for the primary keyword
- Note for each: title tag, meta description, content format (list / guide / comparison / definition), estimated word count, domain authority level, publish/update date
- What is the search intent? (informational / navigational / commercial / transactional)
- What does Google's featured snippet say? (our content must match or beat this)
- What do the "People Also Ask" questions reveal about what searchers actually want?
- What H2 headings appear across the top 3 results? (these signal what Google considers essential coverage)

### Track C — Competitor Content Audit
- For the top 3 ranking pages: fetch the full content
- Note: word count, structure, depth, freshness, internal links, external links, media used
- What angles or subpoints are they covering well?
- What are they missing, shallow on, or getting wrong? (this is where we win)
- What schema markup do they use? (FAQ, HowTo, Article)

---

## PHASE 2 — BRIEF STRUCTURE

### Metadata
- **Target URL slug:** `/[keyword-slug]` (lowercase, hyphens, no stop words)
- **Title tag:** under 60 chars, primary keyword near the front, brand name at end
- **Meta description:** 145-155 chars, includes primary keyword, a benefit, and an implicit CTA
- **Target word count:** based on SERP analysis (match the top 3, or go 20-30% deeper to outrank)
- **Content format:** based on intent (list post / comprehensive guide / comparison / FAQ / definition)
- **Primary keyword:** [keyword] — place in title, H1, first 100 words, at least one H2, image alt text, URL
- **Secondary keywords:** [list] — distribute naturally throughout (no stuffing)
- **People Also Ask questions to answer:** [list — these become FAQ schema]

### Recommended Schema Markup
- `Article` schema: always on blog posts
- `FAQPage` schema: if the post answers 3+ distinct questions
- `HowTo` schema: if the post is a step-by-step process
- `BreadcrumbList`: always

---

## PHASE 3 — CONTENT OUTLINE

Write a complete, ready-to-execute content outline:

**H1 (matches or closely mirrors the title tag):** [exact H1 text]

**Introduction (100-150 words):**
- Opens with the primary keyword in the first sentence
- States what the reader will learn
- Includes a hook (surprising stat, bold claim, or relatable situation)
- No fluff — gets to value by sentence 3

**[H2: First major section]**
- Covers: [what to include]
- Secondary keyword to use: [keyword]
- Word count target: [~X words]
- Include: [specific data point, example, or stat to include from research]

**[H2: Second major section]**
- [same format]

**[Continue for all major sections]**

**FAQ Section (H2: Frequently Asked Questions)**
- Q: [PAA question 1] → brief answer (2-3 sentences, schema-optimised)
- Q: [PAA question 2] → brief answer
- Q: [continue for 3-5 questions]

**Conclusion (75-100 words):**
- Summarise the key takeaway in 1-2 sentences
- Answer "so what?" — what should the reader do now?
- Internal link to the most relevant next page or lead magnet

---

## PHASE 4 — ON-PAGE SEO CHECKLIST

Deliver a ready-to-use checklist for the writer:

**Before writing:**
- [ ] Primary keyword confirmed and placed in brief
- [ ] Target word count set from SERP analysis
- [ ] Top 3 competitor articles read and gaps identified

**While writing:**
- [ ] Primary keyword in H1, first 100 words, at least one H2
- [ ] Secondary keywords used naturally (not forced) throughout
- [ ] Each H2 covers a distinct angle (no overlapping sections)
- [ ] Every stat or claim has a source link
- [ ] Images have descriptive alt text including keyword where natural
- [ ] Internal links to 3+ relevant existing pages on the site
- [ ] External link to 1 authoritative source (gov, academic, major publication)

**Before publishing:**
- [ ] Title tag under 60 chars
- [ ] Meta description 145-155 chars
- [ ] URL slug is clean (primary keyword, no stop words, no uppercase)
- [ ] Schema markup added (Article + FAQ if applicable)
- [ ] Page loads in under 2.5s (LCP target)
- [ ] Mobile layout checked

---

## PHASE 5 — TOPICAL CLUSTER MAP (bonus)

After the main brief, suggest 5 related posts that would build topical authority around this primary keyword:
- Each should target a long-tail variant or related subtopic
- Together with the primary post, they form a cluster that signals expertise to Google
- Note internal linking direction (each cluster post links back to the pillar)

---

## SELF-CHECK (before delivering)

- [ ] Primary keyword identified and justified (not just guessed)
- [ ] SERP intent correctly identified — format matches what Google is rewarding
- [ ] Outline covers all angles in the top 3 results AND adds at least 2 things they missed
- [ ] All PAA questions addressed in the FAQ section
- [ ] Word count target is based on actual SERP data
- [ ] Schema recommendations are specific to this content type
- [ ] Brief is specific enough that a writer could execute it without a briefing call
