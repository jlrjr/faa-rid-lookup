#!/usr/bin/env python3
"""
FAA Remote ID Database Builder (API-Based)

Builds the complete drone serial number database by querying the FAA API.
This is the authoritative source - no local files required.

Process:
1. Query publicDOCRev API with pagination to get all RID records
2. For each RID, query serialNumbers API to get serial numbers/ranges
3. Build SQLite database optimized for serial number lookups
"""

import sqlite3
import requests
import time
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Tuple, Optional


# FAA API endpoints
FAA_DOCREV_API = "https://uasdoc.faa.gov/api/v1/publicDOCRev"
FAA_SERIAL_API = "https://uasdoc.faa.gov/api/v1/serialNumbers"

# Configuration
ITEMS_PER_PAGE = 100
API_THROTTLE_SECONDS = 5
DEFAULT_DB_PATH = "drone_serials.db"


class BuildStats:
    """Track statistics during build process."""
    def __init__(self):
        self.total_rids = 0
        self.rids_processed = 0
        self.rids_with_serials = 0
        self.exact_serials = 0
        self.serial_ranges = 0
        self.api_calls = 0
        self.errors = 0
        self.start_time = datetime.now()

    def report(self, db_path: str):
        """Generate final build report."""
        elapsed = (datetime.now() - self.start_time).total_seconds()
        minutes = int(elapsed / 60)
        seconds = int(elapsed % 60)

        print("\n" + "=" * 70)
        print("Build Complete!")
        print("=" * 70)
        print(f"Total RID Records: {self.total_rids}")
        print(f"RIDs Processed: {self.rids_processed}")
        print(f"RIDs with Serial Numbers: {self.rids_with_serials}")
        print(f"Exact Serial Numbers: {self.exact_serials}")
        print(f"Serial Ranges: {self.serial_ranges}")
        print(f"Total Records: {self.exact_serials + self.serial_ranges}")
        print(f"API Calls Made: {self.api_calls}")
        print(f"Errors: {self.errors}")
        print(f"Build Time: {minutes}m {seconds}s")

        # Check file size
        if Path(db_path).exists():
            size_kb = Path(db_path).stat().st_size / 1024
            print(f"Database Size: {size_kb:.2f} KB")

        print("=" * 70)


def create_database_schema(conn: sqlite3.Connection) -> None:
    """Create the database schema with tables for exact and range lookups."""
    cursor = conn.cursor()

    # Table for exact serial number matches
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS exact_serials (
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
        )
    """)

    # Table for serial number ranges
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS serial_ranges (
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
        )
    """)

    # Create indices for faster lookups
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_ranges_start ON serial_ranges(serial_start)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_ranges_end ON serial_ranges(serial_end)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_exact_rid ON exact_serials(rid_tracking)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_ranges_rid ON serial_ranges(rid_tracking)")

    # Metadata table to track database build info
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS metadata (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    """)

    conn.commit()


def get_all_rids(stats: BuildStats) -> List[Dict]:
    """
    Fetch all RID records from FAA API using pagination.

    Args:
        stats: BuildStats object to track API calls

    Returns:
        List of all RID records
    """
    all_rids = []
    page_index = 0

    print("Fetching all RID records from FAA API...")
    print(f"Using pagination: {ITEMS_PER_PAGE} items per page\n")

    while True:
        print(f"Fetching page {page_index + 1}...", end=" ", flush=True)

        try:
            # Add throttle before API call (except first call)
            if page_index > 0:
                time.sleep(API_THROTTLE_SECONDS)

            response = requests.get(
                url=FAA_DOCREV_API,
                params={
                    "itemsPerPage": str(ITEMS_PER_PAGE),
                    "pageIndex": str(page_index),
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

            stats.api_calls += 1

            if response.status_code != 200:
                print(f"✗ Error: HTTP {response.status_code}")
                stats.errors += 1
                break

            data = response.json()
            items = data.get("data", {}).get("items", [])

            if not items:
                print("✓ No more records")
                break

            all_rids.extend(items)
            print(f"✓ Found {len(items)} RIDs (total: {len(all_rids)})")

            page_index += 1

        except Exception as e:
            print(f"✗ Error: {e}")
            stats.errors += 1
            break

    stats.total_rids = len(all_rids)
    print(f"\n✓ Retrieved {len(all_rids)} total RID records\n")
    return all_rids


def get_serial_numbers_for_rid(rid_tracking: str, stats: BuildStats) -> Optional[List[Dict]]:
    """
    Fetch serial numbers for a specific RID tracking number.

    Args:
        rid_tracking: The RID tracking number
        stats: BuildStats object to track API calls

    Returns:
        List of serial number records or None
    """
    try:
        time.sleep(API_THROTTLE_SECONDS)

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

        stats.api_calls += 1

        if response.status_code == 200:
            data = response.json()
            items = data.get("data", {}).get("items", [])
            return items if items else None

    except Exception as e:
        print(f"    ✗ Error fetching serials: {e}")
        stats.errors += 1

    return None


def parse_serial_records(serial_items: List[Dict], rid_summary: Dict) -> Tuple[List[Dict], List[Dict]]:
    """
    Parse serial numbers from API into exact serials and ranges.

    Args:
        serial_items: List of serial number items from API
        rid_summary: RID summary data (make, model, etc.)

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

    sync_time = datetime.now().isoformat()

    for serial_item in serial_items:
        value = serial_item.get("value", "").strip()
        mfr_serial = serial_item.get("mfrSerial", "")
        # Get the updatedAt from this specific serial record
        faa_updated_at = serial_item.get("updatedAt", "")

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
                    "synced_at": sync_time,
                    "faa_updated_at": faa_updated_at,
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
                    "synced_at": sync_time,
                    "faa_updated_at": faa_updated_at,
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
                "synced_at": sync_time,
                "faa_updated_at": faa_updated_at,
            })

    return exact_serials, serial_ranges


def insert_records(conn: sqlite3.Connection, exact_serials: List[Dict],
                   serial_ranges: List[Dict], stats: BuildStats) -> None:
    """Insert records into the database."""
    cursor = conn.cursor()

    # Insert exact serial numbers
    for record in exact_serials:
        try:
            cursor.execute("""
                INSERT OR REPLACE INTO exact_serials
                (serial_number, rid_tracking, description, status, make, model,
                 mfr_serial, synced_at, faa_updated_at, deleted)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
            """, (
                record["serial_number"],
                record["rid_tracking"],
                record["description"],
                record["status"],
                record["make"],
                record["model"],
                record["mfr_serial"],
                record["synced_at"],
                record["faa_updated_at"],
            ))
            stats.exact_serials += 1
        except Exception as e:
            print(f"    ✗ Error inserting exact serial: {e}")
            stats.errors += 1

    # Insert serial ranges
    for record in serial_ranges:
        try:
            cursor.execute("""
                INSERT INTO serial_ranges
                (serial_start, serial_end, rid_tracking, description, status,
                 make, model, mfr_serial, synced_at, faa_updated_at, deleted)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
            """, (
                record["serial_start"],
                record["serial_end"],
                record["rid_tracking"],
                record["description"],
                record["status"],
                record["make"],
                record["model"],
                None,  # mfr_serial not applicable for ranges
                record["synced_at"],
                record["faa_updated_at"],
            ))
            stats.serial_ranges += 1
        except Exception as e:
            print(f"    ✗ Error inserting range: {e}")
            stats.errors += 1

    conn.commit()


def store_metadata(conn: sqlite3.Connection, stats: BuildStats) -> None:
    """Store metadata about the database build."""
    cursor = conn.cursor()

    metadata = {
        'build_date': datetime.now().isoformat(),
        'build_method': 'api',
        'total_rids': str(stats.total_rids),
        'exact_serials_count': str(stats.exact_serials),
        'serial_ranges_count': str(stats.serial_ranges),
        'total_records': str(stats.exact_serials + stats.serial_ranges),
        'last_sync_date': datetime.now().isoformat(),
    }

    for key, value in metadata.items():
        cursor.execute("""
            INSERT OR REPLACE INTO metadata (key, value)
            VALUES (?, ?)
        """, (key, value))

    conn.commit()


def build_database(db_path: str = DEFAULT_DB_PATH) -> bool:
    """
    Main function to build the drone serial number database from FAA API.

    Args:
        db_path: Path to the database file to create

    Returns:
        True if successful, False otherwise
    """
    print("=" * 70)
    print("FAA Remote ID Database Builder (API-Based)")
    print("=" * 70)
    print(f"\nDatabase: {db_path}")
    print(f"API Throttle: {API_THROTTLE_SECONDS} seconds between calls")
    print(f"Pagination: {ITEMS_PER_PAGE} records per page\n")

    # Initialize stats
    stats = BuildStats()

    # Step 1: Get all RID records with pagination
    all_rids = get_all_rids(stats)

    if not all_rids:
        print("\n✗ No RID records found. Cannot build database.")
        return False

    # Step 2: Create database
    print(f"Creating database: {db_path}\n")

    # Remove existing database if present
    if Path(db_path).exists():
        print(f"⚠ Removing existing database: {db_path}")
        Path(db_path).unlink()

    conn = sqlite3.connect(db_path)

    try:
        # Create schema
        create_database_schema(conn)

        # Step 3: Process each RID and get serial numbers
        print("Processing RID records and fetching serial numbers...")
        print(f"Estimated time: ~{len(all_rids) * API_THROTTLE_SECONDS / 60:.0f} minutes\n")

        for idx, rid_summary in enumerate(all_rids, 1):
            rid_tracking = rid_summary.get("trackingNumber", "")
            make = rid_summary.get("makeName", "")
            model = rid_summary.get("modelName", "")

            # Progress indicator
            progress = f"[{idx}/{len(all_rids)}]"
            print(f"{progress} {rid_tracking} ({make} {model})...")

            stats.rids_processed += 1

            # Fetch serial numbers for this RID
            serial_items = get_serial_numbers_for_rid(rid_tracking, stats)

            if not serial_items:
                print(f"    ⓘ No serial numbers found")
                continue

            stats.rids_with_serials += 1

            # Parse serials
            exact_serials, serial_ranges = parse_serial_records(serial_items, rid_summary)

            print(f"    ✓ Found {len(exact_serials)} exact, {len(serial_ranges)} ranges")

            # Insert into database
            if exact_serials or serial_ranges:
                insert_records(conn, exact_serials, serial_ranges, stats)

        # Store metadata
        store_metadata(conn, stats)

        # Final report
        stats.report(db_path)

        return True

    except Exception as e:
        print(f"\n✗ Build failed: {e}")
        return False

    finally:
        conn.close()


def main():
    """CLI entry point."""
    import sys
    import argparse

    parser = argparse.ArgumentParser(
        description="Build FAA Remote ID database from API"
    )
    parser.add_argument(
        "--db",
        default=DEFAULT_DB_PATH,
        help="Path to database file (default: drone_serials.db)"
    )

    args = parser.parse_args()

    # Confirm if database exists
    if Path(args.db).exists():
        print(f"\n⚠ Warning: Database already exists: {args.db}")
        response = input("Overwrite it? (yes/no): ").strip().lower()
        if response != "yes":
            print("Build cancelled.")
            sys.exit(0)

    success = build_database(args.db)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
