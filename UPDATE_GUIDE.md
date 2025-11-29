# Database Update Guide

Keep your FAA Remote ID database current with the latest records from the FAA API.

## Quick Start

### First Time Setup

1. **Migrate your existing database** (one-time only):
```bash
python3 migrate_database.py
```

This adds the necessary columns for tracking updates.

2. **Run your first update**:
```bash
# Dry-run to see what would be updated
python3 update_database.py --count 50 --dry-run

# Actually update the database
python3 update_database.py --count 50
```

## Update Strategies

### Weekly Scheduled Updates

Automatically check for updates since last sync:

```bash
# Check updates since last successful sync
python3 update_database.py --since-last-sync

# Or specify days back
python3 update_database.py --days 7
```

Add to cron for weekly updates:
```bash
# Every Monday at 2 AM
0 2 * * 1 cd /path/to/faa-rid-db-scrapper && python3 update_database.py --since-last-sync
```

### Update from Specific Date

```bash
# Get all updates since November 1st, 2025
python3 update_database.py --since 2025-11-01
```

### Check Recent Records

```bash
# Check the 100 most recently updated records
python3 update_database.py --count 100
```

## Command Reference

```
python3 update_database.py [OPTIONS]

Options:
  --db PATH              Path to database file (default: drone_serials.db)
  --count N              Number of recent records to check (default: 50)
  --since YYYY-MM-DD     Check updates since this date
  --days N               Check updates from last N days
  --since-last-sync      Check updates since last successful sync
  --dry-run              Show what would be updated without making changes
```

## How It Works

The update process:

1. **Queries publicDOCRev API** for recently updated RID records
2. **Filters by date** (if specified) to get only new updates
3. **For each RID**, queries the serialNumbers API to get current serial numbers
4. **Updates or adds** records to the local database
5. **Tracks last sync** date for future incremental updates
6. **Rate limits** API calls (5-second throttle) to be respectful to FAA servers

## Understanding the Output

```
======================================================================
FAA Remote ID Database Updater
======================================================================
Checking for updates since: 2025-10-29T19:36:14.064903
Fetching up to 2 recent RID records...

Querying FAA publicDOCRev API...
Found 2 RID records to process

[1/2] Processing RID000000077 (Vision Aerial SwitchBlade-Elite)...
  Updated: 2025-11-28T20:10:03.704Z
  Waiting 5s (rate limit)...
  Fetching serial numbers...
  Found 24 exact serials, 1 ranges
  ✓ Updated

======================================================================
Update Summary
======================================================================
RID Records Checked: 2
RID Records Updated: 2
Exact Serials Added: 24
Exact Serials Updated: 0
Serial Ranges Added: 1
Serial Ranges Updated: 1
Total API Calls: 3
Errors: 0
======================================================================
```

### What Each Line Means:

- **RID Records Checked**: How many RIDs were examined
- **RID Records Updated**: How many had changes
- **Exact Serials Added**: New individual serial numbers
- **Exact Serials Updated**: Existing serials that were modified
- **Serial Ranges Added**: New serial number ranges
- **Serial Ranges Updated**: Existing ranges that were modified
- **Total API Calls**: Number of HTTP requests made
- **Errors**: Failed API calls or processing errors

## Dry-Run Mode

Always test with `--dry-run` first to see what would change:

```bash
python3 update_database.py --count 50 --dry-run
```

Output will show:
```
[DRY RUN] Would add: 1788520001 (RID000000077)
[DRY RUN] Would update range: 1788520100 to 1788529999 (RID000000077)
```

No changes are made to the database in dry-run mode.

## Update vs Insert

The updater uses `INSERT OR REPLACE` to handle both:

- **New records**: Added to database
- **Existing records**: Updated with latest FAA data
- **Deduplication**: Based on serial number + RID tracking number

## Database Schema Changes

The migration adds these fields:

- `faa_updated_at`: Timestamp from FAA when record was last updated
- `deleted`: Flag for records removed from FAA (currently unused)
- `last_sync_date`: Metadata tracking last successful sync

## Performance

- **Rate Limiting**: 5-second delay between API calls
- **Batch Size**: Default 50 records, configurable with `--count`
- **Network**: Requires internet connection
- **Time**: ~10 seconds per RID (5s throttle + API call time)

### Estimated Update Times:

- 10 records: ~2 minutes
- 50 records: ~8 minutes
- 100 records: ~17 minutes

## Troubleshooting

### Database Not Migrated

```
Error: Database needs migration.
Please run: python3 migrate_database.py
```

**Solution**: Run `python3 migrate_database.py` first.

### No Updates Found

```
No updates found.
```

This is normal if:
- No records were updated since your last sync
- Your date filter is too recent
- All recent updates are already in your database

### API Errors

```
✗ No serial data found
```

Possible causes:
- Network connectivity issues
- FAA API temporary unavailability
- RID exists but has no serial numbers registered

The updater continues processing other records even if some fail.

### Rate Limiting

The 5-second throttle is intentional to avoid overwhelming the FAA API. Don't reduce it.

## Best Practices

### For First-Time Users

```bash
# 1. Build initial database from existing data
python3 build_database.py

# 2. Migrate to add update tracking
python3 migrate_database.py

# 3. You're ready to update!
python3 update_database.py --since-last-sync
```

### For Regular Updates

```bash
# Weekly: Check for updates since last sync
python3 update_database.py --since-last-sync

# Or specify time period
python3 update_database.py --days 7
```

### For Testing/Development

```bash
# Always use dry-run first
python3 update_database.py --count 10 --dry-run

# Then run for real
python3 update_database.py --count 10
```

## Integration with WarDragon

After updating your database, the new records are immediately available for lookups:

```python
from drone_serial_lookup import lookup_serial

# Lookup a newly updated serial
result = lookup_serial("1788520001")

# Check when it was last updated by FAA
print(f"Last FAA update: {result.get('faa_updated_at')}")
```

## Automation Examples

### Daily Update Script

```bash
#!/bin/bash
# daily_update.sh

cd /path/to/faa-rid-db-scrapper

# Check for updates from last 2 days
python3 update_database.py --days 2 >> update.log 2>&1

# Email results if there were errors
if grep -q "Errors: [1-9]" update.log; then
    mail -s "FAA DB Update Errors" admin@example.com < update.log
fi
```

### Python Automation

```python
import subprocess
import json
from datetime import datetime

def update_database(days_back=7):
    """Run database update and return statistics."""

    result = subprocess.run([
        'python3', 'update_database.py',
        '--days', str(days_back),
    ], capture_output=True, text=True)

    # Parse output for statistics
    if 'Update Summary' in result.stdout:
        print(f"Update completed at {datetime.now()}")
        print(result.stdout)

    return result.returncode == 0

# Run weekly
if __name__ == "__main__":
    update_database(days_back=7)
```

## Checking Database Status

```bash
# View last sync date
sqlite3 drone_serials.db "SELECT value FROM metadata WHERE key = 'last_sync_date';"

# Count records by update date
sqlite3 drone_serials.db "
  SELECT
    date(faa_updated_at) as update_date,
    COUNT(*) as count
  FROM exact_serials
  WHERE faa_updated_at IS NOT NULL
  GROUP BY date(faa_updated_at)
  ORDER BY update_date DESC
  LIMIT 10;
"

# Find most recently updated records
sqlite3 drone_serials.db "
  SELECT serial_number, make, model, faa_updated_at
  FROM exact_serials
  WHERE faa_updated_at IS NOT NULL
  ORDER BY faa_updated_at DESC
  LIMIT 10;
"
```

## Advanced Usage

### Custom Update Logic

```python
from update_database import (
    get_recent_updates,
    get_serial_numbers_for_rid,
    parse_serial_records,
    update_database as do_update
)
import sqlite3

# Custom filtering logic
recent_rids = get_recent_updates(items_per_page=100)

# Filter for specific manufacturers
skydio_rids = [
    rid for rid in recent_rids
    if 'Skydio' in rid.get('makeName', '')
]

# Process only those
conn = sqlite3.connect('drone_serials.db')
for rid in skydio_rids:
    serial_items = get_serial_numbers_for_rid(rid['trackingNumber'])
    if serial_items:
        exact, ranges = parse_serial_records(
            serial_items,
            rid,
            rid['updatedAt']
        )
        # Process...
```

## FAQ

**Q: How often should I update?**
A: Weekly is usually sufficient. The FAA doesn't update records that frequently.

**Q: Will updates overwrite my data?**
A: Yes, `INSERT OR REPLACE` will update existing records with the latest FAA data. The `faa_updated_at` field tracks when FAA last modified it.

**Q: Can I undo an update?**
A: No automatic undo, but you can restore from a backup. Consider backing up before major updates.

**Q: Does this delete old records?**
A: No, records are never deleted, only updated or added. The `deleted` flag is reserved for future use.

**Q: What if the FAA API is down?**
A: The updater will report errors but continue processing other records. You can re-run later.

**Q: Can I run multiple updates simultaneously?**
A: No, SQLite may lock the database. Run updates sequentially.

## Support

For issues or questions:
- Check the main README.md
- Review error messages carefully
- Use `--dry-run` to test first
- Check database with `sqlite3 drone_serials.db`
