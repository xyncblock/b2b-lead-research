# Feature Spec: Lead Change Detection & Deterioration Alerts

## What It Does
After the initial discovery run, the system maintains a lightweight history of each lead’s key quality metrics in SQLite. On subsequent runs (weekly or monthly), it re-checks previously discovered leads and flags significant changes—score drops, SSL expiration, checkout breakage, platform migrations, or social account removals. It generates a **Changes Report** surfacing leads that have recently deteriorated and become stronger outreach targets.

## Why It’s Useful
Sales timing is everything. A business whose PageSpeed score just dropped 30 points or whose SSL certificate expired yesterday is far more receptive to a “we noticed your site has issues” pitch than one whose problems are a year old. This turns the tool from a static snapshot into a continuous competitive intelligence system, giving the user first-mover advantage on newly distressed leads. It also protects against stale data: a lead scored HOT six months ago may have rebuilt their site and is now COLD.

## How to Implement

1. **Schema:** Add a `lead_snapshots` table to the existing SQLite audit database (`lead_id`, `snapshot_date`, `score`, `has_ssl`, `mobile_friendly`, `page_speed_score`, `platform`, `checkout_functional`, `social_count`).

2. **ChangeDetector class:** After enrichment, query the most recent snapshot for each lead. Compute deltas and emit a `changes` array when thresholds are crossed:
   - Score drop ≥ 10 points
   - SSL flips `true → false`
   - PageSpeed drops ≥ 20 points
   - Checkout flips `true → false`
   - Platform change detected
   - Social count decreases

3. **Pipeline integration:** Add a `--revisit` flag to `pipeline.py`. When set, the pipeline pulls lead IDs from the snapshot table instead of discovering new ones, re-enriches them, runs change detection, and appends new snapshots.

4. **Outputs:**
   - New Excel sheet **“Recent Changes”** with leads sorted by severity (score drop magnitude).
   - New dashboard tab showing a timeline of deterioration events and a “Recently Distressed” filter.
   - Optional Telegram alert when a previously COLD lead drops into HOT territory.

5. **Compliance:** Re-checks respect the same `robots.txt` cache and crawl delays. No new external data sources are introduced, so GDPR/PECR posture remains unchanged.

---
*Estimated effort: 1–2 days. Reuses all existing enrichment and export infrastructure.*
