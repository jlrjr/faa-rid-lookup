# FAA Remote ID Database - Drone Serial Lookup

A lightweight, efficient Python system for looking up drone serial numbers against the FAA Remote ID compliance database. Designed for integration with WarDragon and DragonSync processes.

## Overview

This project builds a complete drone serial number database by querying the FAA API, then provides fast local lookups with optional API fallback for unknown serials. Supports both exact serial number matches and range-based lookups.

## Features

- **API-First**: Builds database directly from authoritative FAA API
- **Fast Local Lookups**: SQLite database with indices for efficient queries
- **Dual Lookup Methods**: Supports both exact serial matches and range-based lookups
- **API Fallback**: Automatically queries FAA API when local database doesn't have a match
- **Auto-Cache**: Optionally adds API results to local database for future offline use
- **Incremental Updates**: Keep database current with recent FAA changes
- **Lightweight**: ~640 KB database file containing 4000+ drone records
- **Easy Integration**: Python module with simple API
- **CLI Interface**: Command-line tool for testing and manual lookups
- **Consistent Response Format**: Returns JSON-compatible dictionaries

## Quick Start

### 1. Install Dependencies

```bash
pip install requests
# or
pip install -r requirements.txt
```

### 2. Build the Database

Build the complete database from the FAA API (~37 minutes with 441 RIDs):

```bash
python3 build_database_from_api.py
```

This will:
- Query the FAA publicDOCRev API for all Remote ID records
- Fetch serial numbers for each RID
- Build an optimized SQLite database
- Take approximately 37 minutes (5-second API throttle)

### 3. Use the Lookup Module

```python
from drone_serial_lookup import lookup_serial

# Look up a drone serial number (local database only)
result = lookup_serial("2146BF3300000000")

if result["found"]:
    print(f"Make: {result['make']}")
    print(f"Model: {result['model']}")
    print(f"Status: {result['status']}")
    print(f"Source: {result['source']}")  # 'local', 'api', or 'none'
else:
    print("Drone not found in database")

# With API fallback for unknown serials
result = lookup_serial("UNKNOWN123", use_api_fallback=True)

# With API fallback AND auto-add to local database
result = lookup_serial("UNKNOWN123", use_api_fallback=True, add_to_db=True)
```

### 4. Use the CLI

```bash
# Look up a specific serial number (local database only)
python3 drone_serial_lookup.py 2146BF3300000000

# Use API fallback if not found locally
python3 drone_serial_lookup.py UNKNOWN123 --api

# Use API fallback and add result to local database
python3 drone_serial_lookup.py UNKNOWN123 --api --add-to-db

# Use a custom database path
python3 drone_serial_lookup.py 1581F5BK000000000001 --db /path/to/custom.db
```

## Database Statistics

Current FAA Remote ID Database:
- **Total RID Records**: 441
- **Exact Serial Numbers**: ~3,900+ records
- **Serial Ranges**: ~250+ ranges
- **Total Records**: ~4,150+
- **Database Size**: ~640 KB
- **Last Build**: Built from FAA API

## Keeping Database Updated

Check for recent updates from the FAA:

```bash
# Check for updates since last sync
python3 update_database.py --since-last-sync

# Check last 7 days
python3 update_database.py --days 7

# Check 50 most recent records
python3 update_database.py --count 50

# Preview changes without modifying database
python3 update_database.py --count 50 --dry-run
```

See [UPDATE_GUIDE.md](UPDATE_GUIDE.md) for detailed update documentation.

## Response Format

All lookups return a dictionary with the following structure:

```json
{
  "found": true,
  "serial_number": "2146BF3300000000",
  "rid_tracking": "RID000002509",
  "description": "Remote ID (RID)",
  "status": "pending",
  "make": "Contixo Inc.",
  "model": "F33",
  "mfr_serial": null,
  "source": "local"
}
```

### Response Fields

- `found` (bool): Whether the serial was found
- `serial_number` (str): The queried serial number
- `rid_tracking` (str|None): FAA RID tracking number
- `description` (str|None): Description (typically "Remote ID (RID)")
- `status` (str|None): Status (e.g., "pending", "accepted")
- `make` (str|None): Manufacturer name
- `model` (str|None): Model name
- `mfr_serial` (str|None): Manufacturer serial number (if provided)
- `source` (str): Data source - "local" (from database), "api" (from FAA API), or "none" (not found)

## Integration with WarDragon/DragonSync

The module is designed to integrate seamlessly with WarDragon and DragonSync workflows:

### Basic Integration (Local Database Only)

```python
from drone_serial_lookup import lookup_serial

# When DroneID provides a serial number
drone_serial = "1581F5BK000000000001"

# Look it up (local database only - no network required)
drone_info = lookup_serial(drone_serial)

# Check if found before parsing
if drone_info["found"]:
    # Use the data in CoT, Lattice, or other sinks
    cot_properties = {
        "manufacturer": drone_info["make"],
        "model": drone_info["model"],
        "faa_rid": drone_info["rid_tracking"],
        "compliance_status": drone_info["status"]
    }
    # Send to your sink...
else:
    # Handle unknown drone
    print(f"Unknown drone: {drone_serial}")
```

### Advanced Integration (With API Fallback)

```python
from drone_serial_lookup import lookup_serial

def process_drone_detection(serial_number, has_internet=True):
    """Process DroneID detection with intelligent lookup strategy."""

    # Always try local database first (fast, no network)
    result = lookup_serial(serial_number, use_api_fallback=False)

    # If not found locally and we have internet, query FAA API
    if not result["found"] and has_internet:
        result = lookup_serial(
            serial_number,
            use_api_fallback=True,
            add_to_db=True  # Cache for future offline use
        )

    # Build enriched data for CoT/Lattice
    enriched = {
        'serial_number': serial_number,
        'manufacturer': result['make'] if result['found'] else 'Unknown',
        'model': result['model'] if result['found'] else 'Unknown',
        'faa_rid': result['rid_tracking'],
        'status': result['status'],
        'data_source': result['source']  # Track where data came from
    }

    return enriched
```

## Testing

Run the comprehensive test suite:

```bash
python3 test_lookups.py
```

The test suite validates:
- Exact serial number lookups
- Range-based lookups (start and end of range)
- Unknown serial handling
- Edge cases (empty strings, whitespace)
- JSON serialization
- Response format consistency

Test API fallback functionality:

```bash
python3 test_api_fallback.py
```

## Project Structure

### Core Files

- **build_database_from_api.py** - Build database from FAA API (run once)
- **drone_serial_lookup.py** - Main lookup module and CLI interface
- **update_database.py** - Update database with recent FAA changes
- **drone_serials.db** - SQLite database (generated by build script)

### Testing & Examples

- **test_lookups.py** - Comprehensive test suite
- **test_api_fallback.py** - API fallback functionality tests
- **example_usage.py** - Usage examples and integration patterns

### Documentation

- **README.md** - This file (overview and quick start)
- **UPDATE_GUIDE.md** - Detailed database update documentation
- **CLI_USAGE_GUIDE.md** - Command-line interface reference

## Database Schema

### exact_serials Table
Stores individual serial numbers with direct lookup capability.

```sql
CREATE TABLE exact_serials (
    serial_number TEXT PRIMARY KEY,
    rid_tracking TEXT,
    description TEXT,
    status TEXT,
    make TEXT,
    model TEXT,
    mfr_serial TEXT,
    synced_at TEXT,
    faa_updated_at TEXT,
    deleted INTEGER DEFAULT 0
);
```

### serial_ranges Table
Stores serial number ranges for manufacturers that register ranges rather than individual serials.

```sql
CREATE TABLE serial_ranges (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    serial_start TEXT NOT NULL,
    serial_end TEXT NOT NULL,
    rid_tracking TEXT,
    description TEXT,
    status TEXT,
    make TEXT,
    model TEXT,
    mfr_serial TEXT,
    synced_at TEXT,
    faa_updated_at TEXT,
    deleted INTEGER DEFAULT 0
);
```

## Performance

The database is optimized for low-throughput, occasional lookups:
- **Exact serial lookups**: O(1) - indexed primary key
- **Range lookups**: O(n) where n = number of ranges (~250)
- **Typical lookup time**: < 1ms for exact matches, < 5ms for range matches

Build time:
- **Initial build**: ~37 minutes (441 RIDs with 5-second API throttle)
- **Updates**: Depends on number of changed records

## Requirements

- Python 3.6+
- requests library (`pip install requests`)
- sqlite3 (included in Python standard library)

## Workflow

### Initial Setup

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Build database from FAA API (~37 minutes)
python3 build_database_from_api.py

# 3. Test lookups
python3 drone_serial_lookup.py 2146BF3300000000
```

### Regular Maintenance

```bash
# Weekly: Check for updates
python3 update_database.py --since-last-sync

# Or check specific time period
python3 update_database.py --days 7
```

### Development/Testing

```bash
# Run test suite
python3 test_lookups.py

# Test API fallback
python3 test_api_fallback.py

# View examples
python3 example_usage.py
```

## Example Lookups

### Known DJI Drone (Range Lookup)
```bash
$ python3 drone_serial_lookup.py 1581F5BK000000000001
============================================================
Drone Serial Lookup Result
============================================================

Serial Number: 1581F5BK000000000001
Found: True
Source: local

RID Tracking: RID000000012
Description: Remote ID (RID)
Status: pending
Make: DJI
Model: M30T
Mfr Serial: None
============================================================
```

### Known Contixo Drone (Exact Match)
```bash
$ python3 drone_serial_lookup.py 2146BF3300000000
============================================================
Drone Serial Lookup Result
============================================================

Serial Number: 2146BF3300000000
Found: True
Source: local

RID Tracking: RID000002509
Description: Remote ID (RID)
Status: pending
Make: Contixo Inc.
Model: F33
Mfr Serial: None
============================================================
```

### Unknown Drone with API Fallback
```bash
$ python3 drone_serial_lookup.py UNKNOWN123 --api
============================================================
Drone Serial Lookup Result
============================================================

Serial Number: UNKNOWN123
Found: False
Source: none

No matching drone found in database.
Tip: Use --api to query the FAA API for unknown serials
============================================================
```

## Manual Database Queries

The SQLite database can be manually queried:

```bash
# Find all DJI drones
sqlite3 drone_serials.db "SELECT * FROM exact_serials WHERE make LIKE '%DJI%';"

# Find all ranges for a specific manufacturer
sqlite3 drone_serials.db "SELECT * FROM serial_ranges WHERE make = 'DJI';"

# Check last sync date
sqlite3 drone_serials.db "SELECT value FROM metadata WHERE key = 'last_sync_date';"

# Count records by manufacturer
sqlite3 drone_serials.db "
  SELECT make, COUNT(*) as count
  FROM exact_serials
  GROUP BY make
  ORDER BY count DESC
  LIMIT 10;
"
```

Database viewers:
- [DB Browser for SQLite](https://sqlitebrowser.org/)
- SQLite command-line: `sqlite3 drone_serials.db`

## Data Source

All data comes directly from the FAA's authoritative API:
- **publicDOCRev API**: Remote ID record information
- **serialNumbers API**: Serial number details

The database is built and updated exclusively from these official sources.

## License

This project works with publicly available FAA Remote ID compliance data.

## Contributing

Contributions welcome! Please:
- Test changes with `test_lookups.py`
- Update documentation
- Follow existing code style
- Add test cases for new functionality

## Support

For issues or questions:
- Check this README and UPDATE_GUIDE.md
- Review error messages carefully
- Use `--dry-run` to test updates first
- Check [GitHub Issues](https://github.com/anthropics/claude-code/issues) for Claude Code questions

## Changelog

### v2.0 - API-First Architecture
- Complete rewrite to use FAA API as authoritative source
- Eliminated file-based scraping approach
- Added automatic pagination for full database builds
- Renamed `scraped_at` to `synced_at` for clarity
- Added `faa_updated_at` tracking
- Improved build process with progress indicators
- ~37 minute initial build time for all 441 RIDs

### v1.0 - Initial Release
- Local database from scraped files
- Basic lookup functionality
- Range-based lookups
