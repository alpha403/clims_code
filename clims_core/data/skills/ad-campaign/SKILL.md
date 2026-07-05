---
name: ad-campaign
description: When the user wants to create, launch, or manage a Meta Facebook or Instagram ad campaign end-to-end including campaign setup, ad sets, audiences, creatives, and budget -- run this skill
---

Set up and launch a complete Meta ad campaign for the following:

**Brief:** $ARGUMENTS

If the brief is missing details, ask for:
- **Brand / Ad Account:** which Meta ad account to use?
- **Offer:** what is being advertised? Landing page URL?
- **Objective:** leads / conversions / traffic / reach / video views / messages
- **Target audience:** location, age, gender, interests, job titles, custom audiences available?
- **Budget:** daily budget and total campaign budget
- **Duration:** start date and end date (or ongoing)
- **Creative assets:** images/videos available, or should copy only be prepared for human to add assets?
- **Pixel / Dataset:** is the Meta Pixel or Conversions API set up on the landing page?

---

## PHASE 1 — ACCOUNT AUDIT

Use the Meta Ads MCP to inspect the account before building anything:

1. Get the ad account details and current status
2. Check existing campaigns — what's running, what's paused, what's spent
3. Check available custom audiences (website visitors, email lists, lookalikes)
4. Check available ad images and videos in the media library
5. Check the pixel/dataset — is it firing on the right events? Any quality issues?
6. Note the account's existing CPM, CPC, and CPL benchmarks from recent campaigns

Report findings before proceeding. Flag any blockers (no pixel, account spending limit, policy flags).

---

## PHASE 2 — CAMPAIGN STRATEGY

Define the full campaign structure before touching the MCP:

**Funnel tier:** Cold (new audiences) / Warm (retargeting) / Hot (existing customers)

**Campaign objective:** map to Meta's objectives:
- Leads -> Leads campaign (Instant Form or website)
- Sales -> Sales campaign (website conversions, pixel event)
- Awareness -> Awareness or Reach
- Messages -> Engagement (Messages)

**Campaign budget optimisation (CBO) vs Ad Set Budget Optimisation (ABO):**
- Use CBO for most campaigns (Meta distributes budget to best-performing ad sets)
- Use ABO only when testing audiences and need equal spend across ad sets

**Audience strategy:**
- Ad Set 1: Broad (location + age + gender only, let Meta find the audience via pixel signals)
- Ad Set 2: Interest targeting (top 3-5 interests from research)
- Ad Set 3: Custom audience retargeting (if available — website visitors, video viewers, email list)
- Ad Set 4: Lookalike audience (if custom audience has 1,000+ people)

---

## PHASE 3 — BUILD THE CAMPAIGN (Meta Ads MCP)

Execute in this exact order:

### Step 1 — Create Campaign
Use `ads_create_campaign` with:
- `name`: "[Brand] - [Objective] - [Date]" (always date-stamp for easy auditing)
- `objective`: correct Meta objective constant
- `status`: PAUSED (never launch live until all ad sets and ads are reviewed)
- `special_ad_categories`: check if housing / credit / employment / social issues applies
- `bid_strategy`: LOWEST_COST_WITHOUT_CAP for most campaigns starting out

### Step 2 — Create Ad Sets
For each audience in the strategy, use `ads_create_ad_set` with:
- `name`: "[Brand] - [Audience Type] - [Date]"
- `targeting`: build the targeting spec from the brief and research
- `optimization_goal`: LEAD_GENERATION / OFFSITE_CONVERSIONS / LINK_CLICKS (match to objective)
- `billing_event`: IMPRESSIONS
- `bid_amount`: leave empty for auto-bid unless account has historical data
- `daily_budget`: in cents (e.g. $20/day = 2000)
- `start_time` / `end_time`: ISO 8601 format
- `status`: PAUSED

### Step 3 — Create Creatives
Use `ads_create_creative` for each ad variant:
- Build the creative spec from the `ad-copy` skill output (or brief)
- For image ads: provide the image hash or upload URL
- For video ads: provide the video ID from the media library
- Set primary_text, headline, description, call_to_action_type
- Set the link (landing page URL with UTM parameters)

UTM parameters to append to all URLs:
`?utm_source=facebook&utm_medium=paid&utm_campaign=[campaign_slug]&utm_content=[ad_name]`

### Step 4 — Create Ads
Use `ads_create_ad` to attach each creative to an ad set:
- `name`: "[Brand] - [Angle] - [Format] - [Date]"
- `status`: PAUSED
- Link the creative_id from Step 3

### Step 5 — Review Everything
Before activating, use `ads_get_ad_preview` to preview each ad. Confirm:
- Visual renders correctly
- Headline and copy are correct
- Landing page URL is correct with UTM params
- CTA button is correct

---

## PHASE 4 — QUALITY CHECKS

Run these checks using the MCP before activating:

- `ads_get_errors` on the ad account — resolve any policy flags
- Check the dataset/pixel quality with `ads_get_dataset_quality` — confirm the conversion event is firing
- `ads_get_opportunity_score` — review any recommendations Meta flags

---

## PHASE 5 — ACTIVATE & MONITOR

Once all checks pass:
1. Activate campaign and ad sets using `ads_activate_entity`
2. Set a calendar reminder to check performance at 48h (let Meta exit the learning phase — needs 50 conversion events per ad set per week to exit)

Deliver a campaign summary:
- Campaign ID and structure overview
- Estimated CPM range based on audience size and budget (from `ads_insights_industry_benchmark`)
- What to watch in the first 48 hours (CTR, frequency, CPC)
- When to kill an underperforming ad set (after 3x target CPA with no conversion)
- When to scale a winning ad set (CPA at or below target for 3 consecutive days)

---

## SELF-CHECK (before reporting done)

- [ ] All campaigns and ad sets are set to PAUSED before review
- [ ] UTM parameters on every ad URL
- [ ] No policy violations flagged
- [ ] Pixel/dataset confirmed firing on the correct event
- [ ] At least 2 creative variants per ad set (never run a single ad)
- [ ] Naming convention consistent across all entities
- [ ] Campaign summary delivered with monitoring instructions
