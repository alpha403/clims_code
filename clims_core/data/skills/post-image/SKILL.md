---
name: post-image
description: When the user wants to design a social media graphic, post image, story image, carousel slide, quote card, announcement graphic, or any visual content for any brand or platform -- run this skill
---

Research and design a complete set of social media graphics for the following:

**Brief:** $ARGUMENTS

If the brief is missing details, ask for:
- **Brand:** name, colors (hex), logo path (if any), fonts (or use system fonts)
- **Platform + format:** Instagram post (1080x1080) / Instagram story (1080x1920) / LinkedIn post (1200x628) / Facebook post (1200x630) / Twitter/X (1600x900) / TikTok thumbnail (1080x1920) / all
- **Content type:** quote card / tip carousel / announcement / stat/number graphic / testimonial / product feature / event / before-after / checklist
- **Copy:** provide the text to feature, or should the agent write it?
- **Tone / style:** bold and minimal / warm and human / dark luxury / clean editorial / energetic / corporate professional

---

## PHASE 1 — DESIGN RESEARCH (run in parallel)

### Track A — Visual Trend Research
- Search Dribbble, Pinterest, and Behance for "[niche] social media graphic" and "[brand style] instagram post design"
- What visual styles are dominating high-performing posts in this niche right now?
- What typography treatment gets the most saves? (Bold single-word overlays / clean editorial / handwritten accent / all-caps headlines)
- What color approaches are winning? (Monochrome + one accent / gradient / high contrast / brand colors only)
- What layout patterns convert to saves and shares? (Rule of thirds / centered hero / grid / overlapping elements)
- Fetch 5-10 reference images that best represent what this brand should look like

### Track B — Copy Research (if copy not provided)
- What is the single most shareable insight, stat, or truth in this niche right now?
- What format makes people save: practical tips / surprising facts / controversial opinions / aspirational statements / how-to steps?
- Write the headline: under 7 words, punchy, standalone value — the kind of line people screenshot
- Write the subheadline or body text if the format requires it

---

## PHASE 2 — DESIGN STRATEGY

Before building, define:
- **Layout:** describe the composition (text placement, visual hierarchy, background treatment)
- **Color palette:** primary bg, text color, accent — from brand brief or research recommendation
- **Typography:** headline font + body font (use system fonts: Segoe UI, Arial, Georgia, or Google Fonts via @import)
- **Visual element:** what is the dominant visual — icon, pattern, photo overlay, illustration, number, or pure typography?
- **Formats to produce:** list each size/platform

---

## PHASE 3 — BUILD THE GRAPHICS

Build each graphic as a self-contained HTML file that renders pixel-perfectly at the target dimensions:

```
post_image_{slug}_{format}.html
```

Requirements for each:
- **Exact canvas size** set via fixed width/height on the root element
- **No external dependencies** — all CSS inline, all fonts via Google Fonts `@import` or system fonts
- **Screenshot-ready** — open in browser, take a screenshot at 1:1 — that IS the final image
- **Brand accurate** — exact hex colors from the brief, not approximations
- **Text is real** — the actual copy, not placeholder

### Single-image formats (quote card, stat, announcement):
- One dominant visual statement
- Clear hierarchy: headline > subheadline > brand mark
- Logo or brand name small in corner
- Nothing competing for attention

### Carousel formats (tips, steps, checklist):
- Slide 1: hook slide (the promise — "5 things you didn't know about X")
- Slides 2-N: one point per slide (consistent layout, varies only in content)
- Final slide: CTA slide ("Follow for more" / "Save this" / "DM us [keyword]")
- Build each slide as a `<section>` in one HTML file, or separate files per slide

### Story format (1080x1920):
- Top third: hook / question / bold statement
- Middle: visual or key content
- Bottom: CTA or brand (sticker-style, not a full footer)
- Leave safe zones: top 250px and bottom 250px should not have critical content (UI overlays)

---

## PHASE 4 — VARIATIONS

For the primary graphic, produce 2 color variations:
1. **Dark version** (dark background, light text) — works as a story or dark-mode feed post
2. **Light version** (light background, dark text) — works as a feed post or carousel

---

## PHASE 5 — USAGE GUIDE

After the graphics, deliver a short usage guide:
- Which format to post where and when
- What caption to pair it with (or trigger `/caption` skill)
- How to save the HTML as an image (open in Chrome → Ctrl+Shift+I → right-click the canvas element → "Capture node screenshot", or use a headless browser)
- A/B test suggestion: which variation to test first and what metric to watch (saves, shares, profile visits)

---

## SELF-CHECK (before delivering)

- [ ] Every graphic renders at the exact target pixel dimensions
- [ ] Brand colors are exact hex values from the brief — no approximations
- [ ] Text is readable at the intended display size (minimum 40px on a 1080px canvas for body text)
- [ ] No critical content in story safe zones (top/bottom 250px)
- [ ] Carousel has a hook slide and a CTA slide
- [ ] Both dark and light variations delivered for the primary graphic
- [ ] All HTML files are self-contained (no broken external links)
- [ ] Usage guide includes how to export to image
