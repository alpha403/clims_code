---
name: report
description: When the user wants a marketing performance report, analytics report, ad performance review, social media report, or any data-driven review of what is and is not working -- run this skill
---

Pull data and produce a complete marketing performance report for the following:

**Brief:** $ARGUMENTS

If the brief is missing details, ask for:
- **Brand / accounts:** which GA4 property, Meta ad account, social profiles?
- **Timeframe:** this week / this month / last 30 days / last quarter / custom range
- **Channels to cover:** organic social / paid Meta / website / email / all
- **Goal of the report:** understand what's working / present to a client / decide what to cut / plan next month
- **Benchmark:** compare to previous period, a target, or industry average?

---

## PHASE 1 — DATA COLLECTION (run all channels in parallel)

### Channel A — Meta Ads Performance
Use the Meta Ads MCP to pull:
- `ads_get_ad_entities` — list all active and paused campaigns in the period
- `ads_insights_performance_trend` — overall account performance trend
- For each campaign: impressions, reach, CPM, link clicks, CTR, CPC, leads/conversions, CPL/CPA, amount spent, ROAS (if applicable)
- `ads_insights_anomaly_signal` — any anomalies the platform has detected
- `ads_insights_advertiser_context` — account health signals
- Best-performing ad (lowest CPA or highest ROAS) — extract its copy and creative direction
- Worst-performing ad — extract what failed

### Channel B — Website Performance (GA4)
Use the GA4 MCP tool to pull:
- Sessions, users, new users for the period vs prior period
- Top 5 traffic sources (organic, paid, social, direct, referral) — sessions and conversion rate per source
- Top 5 landing pages — sessions, bounce rate, average engagement time, conversions
- Primary conversion event count and conversion rate
- Device split (mobile vs desktop) — if mobile conversion rate is significantly lower, flag it
- Geographic breakdown if relevant

### Channel C — Organic Social Performance
For each active platform (Instagram, Facebook, LinkedIn, TikTok):
- Reach, impressions, follower growth, engagement rate for the period
- Top 3 posts by reach and by engagement (note what made them work)
- Bottom 3 posts (note what fell flat)
- Profile visits and link-in-bio clicks (if trackable)

### Channel D — Email Performance (if applicable)
Pull from the ESP (describe what data to look for if no direct MCP):
- Emails sent, open rate, click rate, unsubscribe rate for the period
- Best-performing email (highest open rate + highest CTR) — note subject line
- Sequence performance: where in the funnel are people dropping off?

---

## PHASE 2 — SYNTHESIS & ANALYSIS

### What's Working (keep and scale)
List the top 3-5 things producing the best results this period. Be specific:
- "The [angle] ad in the [campaign] campaign achieved [CPA] — 40% below target"
- "The [post type] posts averaged [X%] engagement rate — 2x the account average"

### What's Not Working (cut, pause, or fix)
List the top 3-5 underperformers with a diagnosis:
- "[Campaign] spent $[X] with 0 conversions — likely audience mismatch or landing page issue"
- "[Post format] averaged [X%] engagement — below benchmark, pausing this format"

### Trend Signals
- Is performance improving or declining week-over-week?
- Any sudden drops? (Could signal ad fatigue, algorithm change, seasonal dip)
- Any sudden spikes? (What caused them? Can it be repeated?)

### Cross-Channel Observations
- Which channel is driving the most qualified traffic? (highest conversion rate, not just volume)
- Are there attribution gaps? (traffic arriving but not converting — check the funnel)
- Is there audience overlap causing ad fatigue?

---

## PHASE 3 — RECOMMENDATIONS

Prioritised action list — not observations, but specific next actions:

**This week (quick wins):**
1. [Specific action] — e.g. "Pause [ad name], reallocate $[X]/day to [winning ad]"
2. [Specific action] — e.g. "A/B test a new hook on [top-performing campaign] — current one is fatiguing (frequency > 3)"
3. [Specific action] — e.g. "Fix mobile conversion rate on [landing page] — 78% of traffic is mobile but only 12% of conversions"

**This month (strategic moves):**
1. [Bigger action] — e.g. "Launch retargeting campaign to the [X] website visitors who haven't converted"
2. [Bigger action] — e.g. "Produce 3 more reels in the [top-performing] format that drove [X% engagement]"

**Next quarter (planning):**
1. [Strategic direction] based on trend data

---

## PHASE 4 — REPORT DOCUMENT

Build a clean, readable report as a single `report_{period}.html`:

**Structure:**
- Header: brand name, report period, date generated
- Executive Summary: 3-5 bullets — the most important findings a busy decision-maker needs in 60 seconds
- Channel sections: one section per channel with key metrics in a visual table + 2-3 sentence commentary
- What's Working / What's Not: clear two-column layout
- Recommendations: numbered, prioritised, specific
- Appendix: full data tables for reference

**Design:** clean, minimal, on-brand. Navy/white or brand colors from brief. Tables over walls of text. Use green/red color coding for above/below benchmark metrics. Print-friendly.

---

## SELF-CHECK (before delivering)

- [ ] Data pulled for every channel in the brief — no channel skipped
- [ ] Every metric compared to prior period or a benchmark (raw numbers alone are meaningless)
- [ ] Recommendations are specific and actionable — not "improve engagement"
- [ ] Executive summary can be read in 60 seconds and contains the 3 most important findings
- [ ] Report HTML renders cleanly and is print-ready
- [ ] No vanity metrics reported without context (impressions without CTR, followers without engagement rate)
