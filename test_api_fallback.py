#!/usr/bin/env python3
"""
Test script to demonstrate API fallback functionality.

This script tests the FAA API fallback feature by:
1. Looking up a serial that's in the local database
2. Looking up a serial that requires API fallback
3. Adding an API result to the local database
"""

from drone_serial_lookup import lookup_serial, query_faa_api
import time


def test_local_lookup():
    """Test lookup from local database."""
    print("=" * 70)
    print("TEST 1: Local Database Lookup")
    print("=" * 70)

    serial = "2146BF3300000000"
    result = lookup_serial(serial, use_api_fallback=False)

    print(f"\nSerial: {serial}")
    print(f"Found: {result['found']}")
    print(f"Source: {result['source']}")
    if result['found']:
        print(f"Make: {result['make']}")
        print(f"Model: {result['model']}")


def test_api_query():
    """Test direct API query."""
    print("\n" + "=" * 70)
    print("TEST 2: Direct FAA API Query")
    print("=" * 70)

    serial = "1668BS20FB00N3D4"  # Skydio serial from your example
    print(f"\nQuerying FAA API for: {serial}")
    print("(This may take a few seconds...)")

    result = query_faa_api(serial)

    if result:
        print(f"\n✓ Found in FAA API")
        print(f"RID Tracking: {result['rid_tracking']}")
        print(f"Make: {result['make']}")
        print(f"Model: {result['model']}")
        print(f"Status: {result['status']}")
    else:
        print(f"\n✗ Not found in FAA API")


def test_api_fallback():
    """Test lookup with API fallback."""
    print("\n" + "=" * 70)
    print("TEST 3: Lookup with API Fallback")
    print("=" * 70)

    # This serial should be in local DB, so won't trigger API
    serial1 = "2146BF3300000000"
    print(f"\nLooking up {serial1} (should be local)...")
    result1 = lookup_serial(serial1, use_api_fallback=True)
    print(f"Found: {result1['found']}, Source: {result1['source']}")

    # Try with a potentially unknown serial (you can replace this)
    print("\nNote: For true API fallback, you would need a serial that's")
    print("      in the FAA database but not in your local database.")


def test_add_to_database():
    """Test adding API results to database."""
    print("\n" + "=" * 70)
    print("TEST 4: Add API Results to Database")
    print("=" * 70)

    print("\nThis test would add an API result to your local database.")
    print("To avoid modifying your database during testing, this is")
    print("shown as an example only.")
    print("\nUsage:")
    print("  result = lookup_serial(serial, use_api_fallback=True, add_to_db=True)")
    print("\nOr via CLI:")
    print("  python3 drone_serial_lookup.py <serial> --api --add-to-db")


def demo_wardragon_integration():
    """Demonstrate WarDragon integration pattern."""
    print("\n" + "=" * 70)
    print("TEST 5: WarDragon Integration Pattern")
    print("=" * 70)

    print("""
# WarDragon integration with API fallback:

def process_drone_detection(serial_number, has_internet=True):
    '''Process DroneID detection with FAA database lookup.'''

    # Try local database first (fast, no network required)
    result = lookup_serial(serial_number, use_api_fallback=False)

    # If not found locally and we have internet, try FAA API
    if not result['found'] and has_internet:
        result = lookup_serial(
            serial_number,
            use_api_fallback=True,
            add_to_db=True  # Cache for future use
        )

    # Build enriched data for CoT/Lattice
    if result['found']:
        enriched = {
            'serial_number': serial_number,
            'manufacturer': result['make'],
            'model': result['model'],
            'faa_rid': result['rid_tracking'],
            'status': result['status'],
            'data_source': result['source']  # 'local' or 'api'
        }
        return enriched
    else:
        # Unknown drone
        return {
            'serial_number': serial_number,
            'manufacturer': 'Unknown',
            'model': 'Unknown',
            'faa_rid': None,
            'status': 'unregistered',
            'data_source': 'none'
        }
    """)

    # Actual demonstration
    print("\nActual demonstration:")
    serial = "2146BF3300000000"
    result = lookup_serial(serial, use_api_fallback=True)

    enriched = {
        'serial_number': serial,
        'manufacturer': result['make'] if result['found'] else 'Unknown',
        'model': result['model'] if result['found'] else 'Unknown',
        'faa_rid': result['rid_tracking'],
        'data_source': result['source']
    }

    import json
    print(json.dumps(enriched, indent=2))


def main():
    """Run all tests."""
    print("\n" + "=" * 70)
    print("FAA API FALLBACK FUNCTIONALITY TESTS")
    print("=" * 70)
    print("\nNote: Some tests require internet connectivity to query the FAA API.")
    print("      Network errors will be handled gracefully.\n")

    time.sleep(1)

    test_local_lookup()
    time.sleep(0.5)

    test_api_query()
    time.sleep(0.5)

    test_api_fallback()
    time.sleep(0.5)

    test_add_to_database()
    time.sleep(0.5)

    demo_wardragon_integration()

    print("\n" + "=" * 70)
    print("TESTS COMPLETE")
    print("=" * 70 + "\n")


if __name__ == "__main__":
    main()
