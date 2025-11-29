#!/usr/bin/env python3
"""
Drone Serial Number Lookup Module

Provides fast lookups of drone serial numbers against the FAA Remote ID
compliance database. Supports both exact serial matches and range-based lookups.
Falls back to FAA API when local database doesn't have a match.

Usage:
    from drone_serial_lookup import lookup_serial

    # Local database only
    result = lookup_serial("2146BF3300000000")

    # With API fallback and auto-add to database
    result = lookup_serial("2146BF3300000000", use_api_fallback=True, add_to_db=True)

    if result["found"]:
        print(f"Make: {result['make']}, Model: {result['model']}")
        print(f"Source: {result['source']}")  # 'local' or 'api'
"""

import sqlite3
import requests
from pathlib import Path
from typing import Optional, Dict, Any
from datetime import datetime


# Default database path (relative to this module)
DEFAULT_DB_PATH = Path(__file__).parent / "drone_serials.db"

# FAA API endpoint
FAA_API_URL = "https://uasdoc.faa.gov/api/v1/serialNumbers"


def query_faa_api(serial_number: str) -> Optional[Dict[str, Any]]:
    """
    Query the FAA API for a serial number.

    Args:
        serial_number: The serial number to search for

    Returns:
        Dictionary with drone info if found, None otherwise
    """
    try:
        response = requests.get(
            url=FAA_API_URL,
            params={
                "orderBy[0]": "updatedAt",
                "orderBy[1]": "DESC",
                "findBy": "serialNumber",
                "serialNumber": serial_number,
            },
            headers={
                "Accept": "application/json",
                "Content-Type": "application/json",
                "client": "external",
            },
            timeout=10
        )

        if response.status_code == 200:
            data = response.json()
            items = data.get("data", {}).get("items", [])

            if items:
                # Use the first item (most recently updated)
                item = items[0]
                return {
                    "rid_tracking": item.get("trackingNumber"),
                    "description": item.get("docType", "").upper() if item.get("docType") else None,
                    "status": item.get("status"),
                    "make": item.get("makeName"),
                    "model": item.get("modelName"),
                    "mfr_serial": serial_number,  # The queried serial
                    "updated_at": item.get("updatedAt"),
                }

    except requests.exceptions.RequestException:
        # Network error or timeout - silently fail
        pass
    except Exception:
        # Any other error - silently fail
        pass

    return None


def add_serial_to_database(serial_number: str, drone_info: Dict[str, Any],
                           db_path: str) -> bool:
    """
    Add a newly discovered serial number to the database.

    Args:
        serial_number: The serial number
        drone_info: Dictionary with drone information from API
        db_path: Path to the database

    Returns:
        True if successfully added, False otherwise
    """
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        cursor.execute("""
            INSERT OR REPLACE INTO exact_serials
            (serial_number, rid_tracking, description, status, make, model,
             mfr_serial, scraped_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            serial_number,
            drone_info.get("rid_tracking"),
            drone_info.get("description"),
            drone_info.get("status"),
            drone_info.get("make"),
            drone_info.get("model"),
            drone_info.get("mfr_serial"),
            datetime.now().isoformat()
        ))

        conn.commit()
        conn.close()
        return True

    except sqlite3.Error:
        return False


def lookup_serial(serial_number: str, db_path: Optional[str] = None,
                 use_api_fallback: bool = False, add_to_db: bool = False) -> Dict[str, Any]:
    """
    Look up a drone serial number in the FAA Remote ID database.

    Args:
        serial_number: The drone serial number to look up
        db_path: Optional path to the database file. If None, uses default location.
        use_api_fallback: If True, query FAA API when local DB has no match
        add_to_db: If True, add API results to local database (requires use_api_fallback=True)

    Returns:
        A dictionary containing:
        - found (bool): Whether the serial was found
        - serial_number (str): The queried serial number
        - rid_tracking (str|None): FAA RID tracking number
        - description (str|None): Description (typically "Remote ID (RID)")
        - status (str|None): Status (e.g., "pending", "accepted")
        - make (str|None): Manufacturer name
        - model (str|None): Model name
        - mfr_serial (str|None): Manufacturer serial number
        - source (str): 'local' if found in DB, 'api' if from FAA API, 'none' if not found

    Example:
        >>> result = lookup_serial("2146BF3300000000")
        >>> if result["found"]:
        ...     print(f"{result['make']} {result['model']}")
    """
    # Use default database path if not specified
    if db_path is None:
        db_path = str(DEFAULT_DB_PATH)

    # Check if database exists
    if not Path(db_path).exists():
        raise FileNotFoundError(
            f"Database not found at {db_path}. "
            "Please run build_database.py first to create the database."
        )

    # Initialize result with not found
    result = {
        "found": False,
        "serial_number": serial_number,
        "rid_tracking": None,
        "description": None,
        "status": None,
        "make": None,
        "model": None,
        "mfr_serial": None,
        "source": "none"
    }

    # Strip whitespace from input
    serial_number = serial_number.strip()

    if not serial_number:
        return result

    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # First, try exact match
        cursor.execute("""
            SELECT rid_tracking, description, status, make, model, mfr_serial
            FROM exact_serials
            WHERE serial_number = ?
        """, (serial_number,))

        row = cursor.fetchone()

        if row:
            # Exact match found
            result.update({
                "found": True,
                "rid_tracking": row[0],
                "description": row[1],
                "status": row[2],
                "make": row[3],
                "model": row[4],
                "mfr_serial": row[5],
                "source": "local"
            })
            conn.close()
            return result

        # If no exact match, try range lookup
        cursor.execute("""
            SELECT rid_tracking, description, status, make, model, mfr_serial,
                   serial_start, serial_end
            FROM serial_ranges
            ORDER BY serial_start
        """)

        for row in cursor.fetchall():
            serial_start = row[6]
            serial_end = row[7]

            # Check if the serial falls within this range
            # Using string comparison which works for alphanumeric serials
            if serial_start <= serial_number <= serial_end:
                result.update({
                    "found": True,
                    "rid_tracking": row[0],
                    "description": row[1],
                    "status": row[2],
                    "make": row[3],
                    "model": row[4],
                    "mfr_serial": row[5],
                    "source": "local"
                })
                break

        conn.close()

        # If not found locally and API fallback is enabled, try FAA API
        if not result["found"] and use_api_fallback:
            api_result = query_faa_api(serial_number)

            if api_result:
                result.update({
                    "found": True,
                    "rid_tracking": api_result["rid_tracking"],
                    "description": api_result["description"],
                    "status": api_result["status"],
                    "make": api_result["make"],
                    "model": api_result["model"],
                    "mfr_serial": api_result["mfr_serial"],
                    "source": "api"
                })

                # Optionally add to database
                if add_to_db:
                    add_serial_to_database(serial_number, api_result, db_path)

    except sqlite3.Error as e:
        print(f"Database error: {e}")
    except Exception as e:
        print(f"Unexpected error: {e}")

    return result


def get_database_stats(db_path: Optional[str] = None) -> Dict[str, Any]:
    """
    Get statistics about the database.

    Args:
        db_path: Optional path to the database file

    Returns:
        Dictionary with database statistics
    """
    if db_path is None:
        db_path = str(DEFAULT_DB_PATH)

    if not Path(db_path).exists():
        raise FileNotFoundError(f"Database not found at {db_path}")

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    stats = {}

    # Get metadata
    cursor.execute("SELECT key, value FROM metadata")
    for key, value in cursor.fetchall():
        stats[key] = value

    # Get actual counts
    cursor.execute("SELECT COUNT(*) FROM exact_serials")
    stats['exact_serials_actual'] = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM serial_ranges")
    stats['serial_ranges_actual'] = cursor.fetchone()[0]

    conn.close()

    return stats


def main():
    """CLI interface for testing lookups."""
    import sys
    import argparse

    parser = argparse.ArgumentParser(
        description="Look up drone serial numbers in FAA Remote ID database"
    )
    parser.add_argument("serial_number", help="Drone serial number to look up")
    parser.add_argument("--db", help="Path to database file (optional)")
    parser.add_argument("--api", action="store_true",
                       help="Use FAA API fallback if not found locally")
    parser.add_argument("--add-to-db", action="store_true",
                       help="Add API results to local database (requires --api)")

    args = parser.parse_args()

    # Validate arguments
    if args.add_to_db and not args.api:
        print("Error: --add-to-db requires --api to be enabled")
        sys.exit(1)

    try:
        result = lookup_serial(
            args.serial_number,
            db_path=args.db,
            use_api_fallback=args.api,
            add_to_db=args.add_to_db
        )

        print("\n" + "=" * 60)
        print("Drone Serial Lookup Result")
        print("=" * 60)
        print(f"\nSerial Number: {result['serial_number']}")
        print(f"Found: {result['found']}")
        print(f"Source: {result['source']}")

        if result['found']:
            print(f"\nRID Tracking: {result['rid_tracking']}")
            print(f"Description: {result['description']}")
            print(f"Status: {result['status']}")
            print(f"Make: {result['make']}")
            print(f"Model: {result['model']}")
            print(f"Mfr Serial: {result['mfr_serial']}")

            if result['source'] == 'api' and args.add_to_db:
                print("\n✓ Added to local database")
        else:
            print("\nNo matching drone found in database.")
            if not args.api:
                print("Tip: Use --api to query the FAA API for unknown serials")

        print("=" * 60 + "\n")

    except FileNotFoundError as e:
        print(f"\nError: {e}\n")
        sys.exit(1)
    except Exception as e:
        print(f"\nUnexpected error: {e}\n")
        sys.exit(1)


if __name__ == "__main__":
    main()
