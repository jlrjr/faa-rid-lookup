#!/usr/bin/env python3
"""
FAA Remote ID Database Updater

Fetches recently updated RID records from the FAA API and updates the local database.
Supports incremental updates to keep the database current.
"""

import sqlite3
import requests
import time
import argparse
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple


# FAA API endpoints
FAA_DOCREV_API = "https://uasdoc.faa.gov/api/v1/publicDOCRev"
FAA_SERIAL_API = "https://uasdoc.faa.gov/api/v1/serialNumbers"

# Rate limiting
API_THROTTLE_SECONDS = 5

# Default database path
DEFAULT_DB_PATH = "drone_serials.db"


class UpdateStats:
    """Track statistics during update process."""
    def __init__(self):
        self.rids_checked = 0
        self.rids_updated = 0
        self.serials_added = 0
        self.serials_updated = 0
        self.ranges_added = 0
        self.ranges_updated = 0
        self.api_calls = 0
        self.errors = 0

    def report(self):
        """Generate a summary report."""
        print("\n" + "=" * 70)
        print("Update Summary")
        print("=" * 70)
        print(f"RID Records Checked: {self.rids_checked}")
        print(f"RID Records Updated: {self.rids_updated}")
        print(f"Exact Serials Added: {self.serials_added}")
        print(f"Exact Serials Updated: {self.serials_updated}")
        print(f"Serial Ranges Added: {self.ranges_added}")
        print(f"Serial Ranges Updated: {self.ranges_updated}")
        print(f"Total API Calls: {self.api_calls}")
        print(f"Errors: {self.errors}")
        print("=" * 70)


def get_recent_updates(items_per_page: int = 50,
                       since_date: Optional[str] = None) -> List[Dict]:
    """
    Fetch recently updated RID records from FAA API.

    Args:
        items_per_page: Number of records to retrieve
        since_date: ISO format date to filter updates (not used in API, filtering done locally)

    Returns:
        List of RID records with update information
    """
    try:
        response = requests.get(
            url=FAA_DOCREV_API,
            params={
                "itemsPerPage": str(items_per_page),
                "pageIndex": "0",
                "orderBy[0][0]": "updatedAt",
                "orderBy[0][1]": "DESC",
                "docType": "rid",
            },
            headers={
                "Accept": "application/json",
                "Content-Type": "application/json",
                "client": "external",
            },
            timeout=30
        )

        if response.status_code == 200:
            data = response.json()
            items = data.get("data", {}).get("items", [])

            # Filter by date if provided
            if since_date:
                filtered = []
                # Parse cutoff date, handling both timezone-aware and naive
                cutoff_str = since_date.replace('Z', '+00:00')
                if '+' not in cutoff_str and cutoff_str.count(':') == 2:
                    # Naive datetime, just compare strings
                    cutoff = since_date.split('+')[0].split('Z')[0]
                    for item in items:
                        updated_at = item.get("updatedAt", "")
                        if updated_at:
                            item_date_str = updated_at.split('+')[0].split('Z')[0]
                            if item_date_str > cutoff:
                                filtered.append(item)
                else:
                    cutoff = datetime.fromisoformat(cutoff_str)
                    for item in items:
                        updated_at = item.get("updatedAt", "")
                        if updated_at:
                            item_date = datetime.fromisoformat(updated_at.replace('Z', '+00:00'))
                            if item_date > cutoff:
                                filtered.append(item)
                return filtered

            return items

    except Exception as e:
        print(f"Error fetching recent updates: {e}")

    return []


def get_serial_numbers_for_rid(rid_tracking: str) -> Optional[List[Dict]]:
    """
    Fetch serial numbers for a specific RID tracking number.

    Args:
        rid_tracking: The RID tracking number (e.g., "RID000000001")

    Returns:
        List of serial number records or None
    """
    try:
        response = requests.get(
            url=FAA_SERIAL_API,
            params={
                "snapshot": "true",
                "isPublic": "true",
                "findBy": "docTrackingNumber",
                "docTrackingNumber": rid_tracking,
            },
            headers={
                "Accept": "application/json",
                "Content-Type": "application/json",
                "client": "external",
            },
            timeout=30
        )

        if response.status_code == 200:
            data = response.json()
            items = data.get("data", {}).get("items", [])
            return items if items else None

    except Exception as e:
        print(f"  Error fetching serials for {rid_tracking}: {e}")

    return None


def parse_serial_records(serial_items: List[Dict], rid_summary: Dict, updated_at: str) -> Tuple[List[Dict], List[Dict]]:
    """
    Parse serial numbers from API into exact serials and ranges.

    Args:
        serial_items: List of serial number items from API
        rid_summary: RID summary data (make, model, etc.)
        updated_at: ISO timestamp of when this record was updated

    Returns:
        Tuple of (exact_serials, serial_ranges)
    """
    exact_serials = []
    serial_ranges = []

    # Extract basic info from RID summary
    rid_tracking = rid_summary.get("trackingNumber", "")
    make = rid_summary.get("makeName", "")
    model = rid_summary.get("modelName", "")
    status = rid_summary.get("status", "")
    doc_type = "Remote ID (RID)"

    for serial_item in serial_items:
        value = serial_item.get("value", "").strip()
        mfr_serial = serial_item.get("mfrSerial", "")

        # Determine if range or exact based on value format
        if value and '-' in value and not value.startswith('-'):
            # Range from value field (e.g., "ABC001-ABC999")
            parts = value.split('-', 1)  # Split only on first dash
            if len(parts) == 2:
                serial_ranges.append({
                    "rid_tracking": rid_tracking,
                    "description": doc_type,
                    "status": status,
                    "make": make,
                    "model": model,
                    "serial_start": parts[0].strip(),
                    "serial_end": parts[1].strip(),
                    "faa_updated_at": updated_at,
                })
            else:
                # Can't parse range, treat as exact
                exact_serials.append({
                    "rid_tracking": rid_tracking,
                    "description": doc_type,
                    "status": status,
                    "make": make,
                    "model": model,
                    "serial_number": value,
                    "mfr_serial": mfr_serial if mfr_serial else None,
                    "faa_updated_at": updated_at,
                })
        elif value:
            # Exact serial
            exact_serials.append({
                "rid_tracking": rid_tracking,
                "description": doc_type,
                "status": status,
                "make": make,
                "model": model,
                "serial_number": value,
                "mfr_serial": mfr_serial if mfr_serial else None,
                "faa_updated_at": updated_at,
            })

    return exact_serials, serial_ranges


def update_database(conn: sqlite3.Connection, exact_serials: List[Dict],
                   serial_ranges: List[Dict], stats: UpdateStats, dry_run: bool = False):
    """
    Update the database with new/updated serial records.

    Args:
        conn: Database connection
        exact_serials: List of exact serial records
        serial_ranges: List of serial range records
        stats: UpdateStats object to track changes
        dry_run: If True, don't actually modify database
    """
    cursor = conn.cursor()

    # Update exact serials
    for record in exact_serials:
        serial = record["serial_number"]
        rid = record["rid_tracking"]

        # Check if exists
        cursor.execute("""
            SELECT serial_number FROM exact_serials
            WHERE serial_number = ? AND rid_tracking = ?
        """, (serial, rid))

        exists = cursor.fetchone() is not None

        if dry_run:
            if exists:
                print(f"  [DRY RUN] Would update: {serial} ({rid})")
                stats.serials_updated += 1
            else:
                print(f"  [DRY RUN] Would add: {serial} ({rid})")
                stats.serials_added += 1
        else:
            cursor.execute("""
                INSERT OR REPLACE INTO exact_serials
                (serial_number, rid_tracking, description, status, make, model,
                 mfr_serial, synced_at, faa_updated_at, deleted)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
            """, (
                serial,
                record["rid_tracking"],
                record["description"],
                record["status"],
                record["make"],
                record["model"],
                record["mfr_serial"],
                datetime.now().isoformat(),
                record["faa_updated_at"],
            ))

            if exists:
                stats.serials_updated += 1
            else:
                stats.serials_added += 1

    # Update serial ranges
    for record in serial_ranges:
        start = record["serial_start"]
        end = record["serial_end"]
        rid = record["rid_tracking"]

        # Check if exists
        cursor.execute("""
            SELECT id FROM serial_ranges
            WHERE serial_start = ? AND serial_end = ? AND rid_tracking = ?
        """, (start, end, rid))

        exists = cursor.fetchone() is not None

        if dry_run:
            if exists:
                print(f"  [DRY RUN] Would update range: {start} to {end} ({rid})")
                stats.ranges_updated += 1
            else:
                print(f"  [DRY RUN] Would add range: {start} to {end} ({rid})")
                stats.ranges_added += 1
        else:
            cursor.execute("""
                INSERT OR REPLACE INTO serial_ranges
                (serial_start, serial_end, rid_tracking, description, status,
                 make, model, mfr_serial, synced_at, faa_updated_at, deleted)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
            """, (
                start,
                end,
                record["rid_tracking"],
                record["description"],
                record["status"],
                record["make"],
                record["model"],
                None,
                datetime.now().isoformat(),
                record["faa_updated_at"],
            ))

            if exists:
                stats.ranges_updated += 1
            else:
                stats.ranges_added += 1

    if not dry_run:
        conn.commit()


def get_last_sync_date(conn: sqlite3.Connection) -> Optional[str]:
    """Get the last sync date from metadata."""
    cursor = conn.cursor()
    cursor.execute("SELECT value FROM metadata WHERE key = 'last_sync_date'")
    result = cursor.fetchone()
    return result[0] if result else None


def update_last_sync_date(conn: sqlite3.Connection, dry_run: bool = False):
    """Update the last sync date in metadata."""
    if dry_run:
        print("\n[DRY RUN] Would update last_sync_date")
        return

    cursor = conn.cursor()
    cursor.execute("""
        INSERT OR REPLACE INTO metadata (key, value)
        VALUES ('last_sync_date', ?)
    """, (datetime.now().isoformat(),))
    conn.commit()


def run_update(db_path: str, count: int = 50, since_date: Optional[str] = None,
              days_back: Optional[int] = None, dry_run: bool = False):
    """
    Main update function.

    Args:
        db_path: Path to database file
        count: Number of recent records to check
        since_date: ISO date to check updates since
        days_back: Number of days back to check
        dry_run: If True, show what would happen without modifying database
    """
    print("=" * 70)
    print("FAA Remote ID Database Updater")
    print("=" * 70)

    if dry_run:
        print("\n*** DRY RUN MODE - No changes will be made ***\n")

    # Check database exists
    if not Path(db_path).exists():
        print(f"\nError: Database not found at {db_path}")
        print("Please run build_database.py first.\n")
        return

    # Connect to database
    conn = sqlite3.connect(db_path)

    # Check if migrations applied
    cursor = conn.cursor()
    cursor.execute("PRAGMA table_info(exact_serials)")
    columns = [col[1] for col in cursor.fetchall()]

    if 'faa_updated_at' not in columns:
        print("\nError: Database needs migration.")
        print("Please run: python3 migrate_database.py\n")
        conn.close()
        return

    # Determine date filter
    filter_date = since_date
    if days_back:
        filter_date = (datetime.now() - timedelta(days=days_back)).isoformat()
    elif not since_date:
        # Use last sync date
        last_sync = get_last_sync_date(conn)
        if last_sync:
            filter_date = last_sync
            print(f"\nLast sync: {last_sync}")
        else:
            print("\nNo previous sync found. Fetching recent records...")

    if filter_date:
        print(f"Checking for updates since: {filter_date}")

    print(f"Fetching up to {count} recent RID records...\n")

    # Initialize stats
    stats = UpdateStats()

    # Fetch recent updates
    print("Querying FAA publicDOCRev API...")
    recent_rids = get_recent_updates(items_per_page=count, since_date=filter_date)
    stats.api_calls += 1

    if not recent_rids:
        print("No updates found.")
        conn.close()
        return

    print(f"Found {len(recent_rids)} RID records to process\n")

    # Process each RID
    for idx, rid_summary in enumerate(recent_rids, 1):
        rid_tracking = rid_summary.get("trackingNumber", "")
        updated_at = rid_summary.get("updatedAt", "")
        make = rid_summary.get("makeName", "")
        model = rid_summary.get("modelName", "")

        print(f"[{idx}/{len(recent_rids)}] Processing {rid_tracking} ({make} {model})...")
        print(f"  Updated: {updated_at}")

        stats.rids_checked += 1

        # Rate limiting
        if stats.api_calls > 0:
            print(f"  Waiting {API_THROTTLE_SECONDS}s (rate limit)...")
            time.sleep(API_THROTTLE_SECONDS)

        # Fetch serial numbers for this RID
        print(f"  Fetching serial numbers...")
        serial_items = get_serial_numbers_for_rid(rid_tracking)
        stats.api_calls += 1

        if not serial_items:
            print(f"  ✗ No serial data found")
            stats.errors += 1
            continue

        # Parse serials
        exact_serials, serial_ranges = parse_serial_records(serial_items, rid_summary, updated_at)

        print(f"  Found {len(exact_serials)} exact serials, {len(serial_ranges)} ranges")

        if exact_serials or serial_ranges:
            stats.rids_updated += 1
            update_database(conn, exact_serials, serial_ranges, stats, dry_run)
            print(f"  ✓ Updated")
        else:
            print(f"  - No serial numbers to update")

    # Update last sync date
    if not dry_run:
        update_last_sync_date(conn, dry_run)

    conn.close()

    # Report
    stats.report()

    if dry_run:
        print("\n*** DRY RUN COMPLETE - No actual changes were made ***")


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Update FAA Remote ID database with recent changes"
    )

    parser.add_argument(
        "--db",
        default=DEFAULT_DB_PATH,
        help="Path to database file (default: drone_serials.db)"
    )

    parser.add_argument(
        "--count",
        type=int,
        default=50,
        help="Number of recent records to check (default: 50)"
    )

    parser.add_argument(
        "--since",
        help="Check updates since this date (ISO format: 2025-11-01)"
    )

    parser.add_argument(
        "--days",
        type=int,
        help="Check updates from last N days"
    )

    parser.add_argument(
        "--since-last-sync",
        action="store_true",
        help="Check updates since last successful sync"
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be updated without making changes"
    )

    args = parser.parse_args()

    # Validate arguments
    if args.since and args.days:
        print("Error: Cannot use both --since and --days")
        return

    if args.since_last_sync and (args.since or args.days):
        print("Error: --since-last-sync cannot be used with --since or --days")
        return

    # Run update
    run_update(
        db_path=args.db,
        count=args.count,
        since_date=args.since,
        days_back=args.days,
        dry_run=args.dry_run
    )


if __name__ == "__main__":
    main()
