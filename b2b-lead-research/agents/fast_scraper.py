#!/usr/bin/env python3
"""
Fast Scraper - Collects leads with rate limiting to avoid blocks
Uses Bing Search (more reliable than DuckDuckGo)
"""

import sys
import json
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from discovery.bing_search import BingSearchCollector

OUTPUT_DIR = Path("/home/expertfox/.openclaw/workspace/b2b-lead-research/scraped_leads")
OUTPUT_DIR.mkdir(exist_ok=True)

KEYWORDS = [
    "e-commerce store UK", "online fashion store UK", "online electronics store UK",
    "UK online retailer", "ecommerce website UK", "online shop UK",
    "UK digital store", "online boutique UK", "UK webshop", "online marketplace UK",
    "UK dropshipping store", "online gift shop UK", "UK handmade store",
    "online jewelry store UK", "UK beauty store online", "online furniture store UK",
    "UK food delivery website", "online pet store UK", "UK sports store online",
    "online toy store UK", "UK bookshop online", "online wine store UK",
]


def run_batch():
    collector = BingSearchCollector()
    hour = datetime.now().hour
    keyword = KEYWORDS[hour % len(KEYWORDS)]
    
    print(f"🔍 [{datetime.now().strftime('%H:%M')}] {keyword}")
    
    try:
        stores = collector.search(keyword, max_results=10)
        if not stores:
            print("   No results")
            return 0
        
        results = []
        for store in stores:
            try:
                emails = collector.extract_emails(store['url'])
                store['emails'] = emails
                store['keyword'] = keyword
                store['scraped_at'] = datetime.now().isoformat()
                results.append(store)
                time.sleep(1)  # 1 second delay between sites
            except:
                pass
        
        if results:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            with open(OUTPUT_DIR / f"batch_{timestamp}.json", 'w') as f:
                json.dump(results, f, indent=2)
            
            valid = sum(1 for r in results if r.get('emails'))
            print(f"   ✅ {len(results)} stores, {valid} with emails")
            return len(results)
        
    except Exception as e:
        print(f"   ❌ {str(e)[:50]}")
    
    return 0


def get_stats():
    today = datetime.now().strftime("%Y-%m-%d")
    total = 0
    with_emails = 0
    
    for file in OUTPUT_DIR.glob("batch_*.json"):
        file_date = datetime.fromtimestamp(file.stat().st_mtime).strftime("%Y-%m-%d")
        if file_date == today:
            with open(file) as f:
                data = json.load(f)
            total += len(data)
            with_emails += sum(1 for d in data if d.get('emails'))
    
    return {"total": total, "with_emails": with_emails}


if __name__ == "__main__":
    count = run_batch()
    stats = get_stats()
    print(f"\n📊 Today: {stats['total']} leads, {stats['with_emails']} with emails")
    print(f"⏳ Target: 200/day")
