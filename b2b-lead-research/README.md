# B2B E-commerce Lead Research Tool

Compliant B2B market research pipeline for identifying e-commerce businesses that need website improvement services.

## Architecture

```
b2b-lead-research/
├── compliance/           # GDPR/PECR compliance layer
│   ├── robots_checker.py    # robots.txt checker with caching
│   ├── audit_logger.py      # SQLite audit trail
│   └── consent_classifier.py # Email classification (generic vs named)
├── discovery/            # Business discovery
│   ├── google_places.py     # Google Places API
│   └── companies_house.py   # UK Companies House API
├── enrichment/           # Website analysis
│   ├── website_analyzer.py  # HTML parsing, platform detection
│   └── pagespeed.py         # Google PageSpeed Insights
├── scoring/              # Quality scoring
│   └── engine.py            # 0-100 scoring with revenue signals
├── exporters/            # Output generation
│   ├── excel.py             # Excel export with summary sheet
│   └── telegram.py          # Telegram delivery
└── pipeline.py           # Main orchestrator
```

## Scoring System (0-100)

| Factor | Points | Description |
|--------|--------|-------------|
| SSL valid | 10 | HTTPS certificate |
| Mobile responsive | 15 | Viewport meta tag |
| Page speed >70 | 15 | Lighthouse performance |
| Modern design | 15 | Schema markup, CSS, favicon |
| Working social links | 10 | Social media presence |
| Checkout functional | 15 | E-commerce functionality |
| Recent content <90d | 10 | Content freshness |
| Professional domain email | 10 | Domain-matched email |

**Priority:**
- 🔥 **HOT** (<40 + revenue signals) - Strong rebuild candidate
- ⚡ **WARM** (40-65) - Growth potential
- ❄️ **COLD** (>65) - Well served

## Setup

```bash
pip install -r requirements.txt
cp .env.example .env
# Edit .env with your API keys
```

### Required API Keys

1. **Google Places API** - [Get key](https://console.cloud.google.com/)
2. **Companies House API** (UK) - [Get key](https://developer.company-information.service.gov.uk/) (free)

### Optional

- **Google PageSpeed API** - Performance scores
- **Telegram Bot** - Report delivery

## Usage

```bash
# Run UK pipeline
python pipeline.py --country UK

# Multiple batches
python pipeline.py --country UK --batches 2
```

## Output

Excel file: `b2b_ecom_research_UK_001_YYYYMMDD.xlsx`

Sheets:
- **All Leads** - Complete dataset
- **HOT Leads** - Immediate targets
- **WARM Leads** - Secondary targets
- **COLD Leads** - Monitor
- **Summary** - Batch stats, compliance metadata

## Compliance

- ✅ GDPR Article 6(1)(f) - Legitimate Interest
- ✅ PECR-compliant email classification
- ✅ Respects robots.txt with audit logging
- ✅ Source URL tracking for erasure requests
- ✅ No consumer data, no LinkedIn scraping

## Dashboard

Streamlit dashboard for filtering and review:

```bash
cd dashboard
pip install -r requirements.txt
streamlit run app.py
```
