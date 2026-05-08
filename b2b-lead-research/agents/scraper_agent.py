#!/usr/bin/env python3
"""
High-Volume Scraper Agent
Target: 200 leads/day
Strategy: Multiple searches every 10 minutes with rotating keywords
"""

import sys
import json
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from discovery.google_search import GoogleSearchCollector

# Search keywords to rotate through
KEYWORDS = [
    "e-commerce store UK",
    "online fashion store UK",
    "online electronics store UK", 
    "UK online retailer",
    "ecommerce website UK",
    "online shop UK",
    "UK digital store",
    "online boutique UK",
    "UK webshop",
    "online marketplace UK",
    "UK dropshipping store",
    "online gift shop UK",
    "UK handmade store",
    "online jewelry store UK",
    "UK beauty store online",
    "online furniture store UK",
    "UK food delivery website",
    "online pet store UK",
    "UK sports store online",
    "online toy store UK",
]

OUTPUT_DIR = Path("/home/expertfox/.openclaw/workspace/b2b-lead-research/scraped_leads")
OUTPUT_DIR.mkdir(exist_ok=True)


def run_scraper_batch():
    """Run one batch of scraping (10-15 leads)."""
    collector = GoogleSearchCollector()
    
    # Pick keyword based on time (rotate through list)
    hour = datetime.now().hour
    keyword_index = hour % len(KEYWORDS)
    keyword = KEYWORDS[keyword_index]
    
    print(f"🔍 [{datetime.now().strftime('%H:%M')}] Searching: {keyword}")
    
    try:
        # Search
        stores = collector.search(keyword, region="uk", max_results=15)
        
        if not stores:
            print("   No results found")
            return 0
        
        # Extract emails for each
        results = []
        for store in stores[:10]:  # Max 10 per batch to stay fast
            try:
                emails = collector.extract_emails(store['url'])
                store['emails'] = emails
                store['keyword'] = keyword
                store['scraped_at'] = datetime.now().isoformat()
                results.append(store)
                time.sleep(0.5)  # Be polite
            except Exception as e:
                continue
        
        # Save batch
        if results:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            batch_file = OUTPUT_DIR / f"batch_{timestamp}.json"
            with open(batch_file, 'w') as f:
                json.dump(results, f, indent=2)
            
            valid_emails = sum(1 for r in results if r.get('emails'))
            print(f"   ✅ {len(results)} stores, {valid_emails} with emails")
            return len(results)
        
        return 0
        
    except Exception as e:
        print(f"   ❌ Error: {e}")
        return 0


def get_daily_stats():
    """Get today's scraping stats."""
    today = datetime.now().strftime("%Y-%m-%d")
    
    total_leads = 0
    total_with_emails = 0
    
    for file in OUTPUT_DIR.glob("batch_*.json"):
        # Check if file is from today
        file_date = datetime.fromtimestamp(file.stat().st_mtime).strftime("%Y-%m-%d")
        if file_date == today:
            with open(file) as f:
                data = json.load(f)
            total_leads += len(data)
            total_with_emails += sum(1 for d in data if d.get('emails'))
    
    return {
        "total_leads": total_leads,
        "with_emails": total_with_emails,
        "batches": len(list(OUTPUT_DIR.glob("batch_*.json")))
    }


def main():
    print("=" * 60)
    print("🚀 HIGH-VOLUME SCRAPER")
    print("Target: 200 leads/day")
    print("=" * 60)
    
    # Run one batch
    count = run_scraper_batch()
    
    # Show stats
    stats = get_daily_stats()
    print(f"\n📊 TODAY'S PROGRESS")
    print(f"   Total leads: {stats['total_leads']}")
    print(f"   With emails: {stats['with_emails']}")
    print(f"   Batches run: {stats['batches']}")
    print(f"   Target: 200/day")
    
    if stats['total_leads'] >= 200:
        print("\n🎉 DAILY TARGET REACHED!")
    else:
        remaining = 200 - stats['total_leads']
        print(f"\n⏳ Need {remaining} more leads today")
    
    return count


if __name__ == "__main__":
    main()
