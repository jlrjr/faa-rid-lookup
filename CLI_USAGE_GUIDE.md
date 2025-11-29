# CLI Usage Guide

Quick reference for using the drone serial number lookup CLI tool.

## Installation

Install required dependencies:
```bash
pip install requests
# or
pip install -r requirements.txt
```

Build the database (first time only):
```bash
python3 build_database.py
```

## Basic Usage

### Local Database Lookup (No Internet Required)

Look up a serial number from the local database:
```bash
python3 drone_serial_lookup.py 2146BF3300000000
```

Output:
```
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

### API Fallback (Internet Required)

If a serial is not in your local database, query the FAA API:
```bash
python3 drone_serial_lookup.py UNKNOWN_SERIAL --api
```

This will:
1. Check the local database first
2. If not found, query the FAA API
3. Return the result from either source

### Add API Results to Database

To cache API results for future offline use:
```bash
python3 drone_serial_lookup.py UNKNOWN_SERIAL --api --add-to-db
```

This will:
1. Check the local database
2. Query the FAA API if not found locally
3. Add the API result to your local database
4. Show confirmation that it was added

## Command-Line Options

```
python3 drone_serial_lookup.py [OPTIONS] SERIAL_NUMBER

Arguments:
  SERIAL_NUMBER       The drone serial number to look up (required)

Options:
  --db PATH          Path to custom database file
  --api              Enable FAA API fallback for unknown serials
  --add-to-db        Add API results to local database (requires --api)
  -h, --help         Show help message
```

## Examples

### Example 1: Known DJI Drone (Range Lookup)
```bash
python3 drone_serial_lookup.py 1581F5BK000000000001
```

Returns:
- Make: DJI
- Model: M30T
- Source: local (from range lookup)

### Example 2: Known Holyton Drone (Your Original Query)
```bash
python3 drone_serial_lookup.py 2003AHT60001781
```

Returns:
- Make: Holyton
- Model: HT60
- Source: local (from range lookup)

### Example 3: Unknown Drone (No API)
```bash
python3 drone_serial_lookup.py NOTFOUND123
```

Returns:
- Found: False
- Tip: Use --api to query the FAA API for unknown serials

### Example 4: Unknown Drone (With API)
```bash
python3 drone_serial_lookup.py UNKNOWN123 --api
```

Returns:
- Found: True/False depending on FAA API result
- Source: api (if found in FAA API)

### Example 5: Query API and Cache Result
```bash
python3 drone_serial_lookup.py NEWDRONE456 --api --add-to-db
```

If found in API:
- Returns drone information
- Adds to local database
- Shows "✓ Added to local database"
- Future queries will use local database (faster, offline)

### Example 6: Custom Database Path
```bash
python3 drone_serial_lookup.py 2146BF3300000000 --db /path/to/custom.db
```

## Integration Tips

### For WarDragon/DragonSync

**Offline/Field Use:**
```bash
# No internet? Use local database only
python3 drone_serial_lookup.py $SERIAL_NUMBER
```

**Online with Auto-Caching:**
```bash
# Has internet? Use API fallback and cache results
python3 drone_serial_lookup.py $SERIAL_NUMBER --api --add-to-db
```

**Scripting:**
```bash
#!/bin/bash
SERIAL=$1

# Check if we have internet connectivity
if ping -c 1 8.8.8.8 &> /dev/null; then
    # Online: use API fallback and cache
    python3 drone_serial_lookup.py "$SERIAL" --api --add-to-db
else
    # Offline: local database only
    python3 drone_serial_lookup.py "$SERIAL"
fi
```

## Response Codes

The CLI uses standard exit codes:
- `0`: Success (drone found or not found, but no errors)
- `1`: Error (missing database, invalid arguments, etc.)

## Performance

- **Local Lookup**: < 1ms for exact matches, < 5ms for range lookups
- **API Fallback**: 1-5 seconds depending on network latency
- **Database Size**: ~636 KB (very portable)

## Troubleshooting

**Database not found:**
```
Error: Database not found at drone_serials.db.
Please run build_database.py first to create the database.
```
Solution: Run `python3 build_database.py`

**API request fails:**
- The tool fails gracefully - returns "not found" instead of crashing
- Check internet connectivity
- FAA API may be temporarily unavailable

**--add-to-db without --api:**
```
Error: --add-to-db requires --api to be enabled
```
Solution: Add `--api` flag when using `--add-to-db`

## Quick Reference

```bash
# Most common commands:

# Local lookup only (fast, offline)
python3 drone_serial_lookup.py <SERIAL>

# With API fallback (online, slower)
python3 drone_serial_lookup.py <SERIAL> --api

# With API + auto-cache (online, builds local DB)
python3 drone_serial_lookup.py <SERIAL> --api --add-to-db

# Show help
python3 drone_serial_lookup.py --help
```
