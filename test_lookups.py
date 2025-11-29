#!/usr/bin/env python3
"""
Test script for drone serial number lookups.

Generates test cases from the database and validates lookup functionality.
"""

import json
import sqlite3
import random
from pathlib import Path
from drone_serial_lookup import lookup_serial, get_database_stats


def get_test_serials(db_path: str = "drone_serials.db") -> dict:
    """
    Extract sample serial numbers from the database for testing.

    Returns:
        Dictionary with 'exact' and 'range' serial numbers
    """
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Get sample exact serials
    cursor.execute("""
        SELECT serial_number, make, model
        FROM exact_serials
        LIMIT 100
    """)
    exact_samples = cursor.fetchall()

    # Get all range records
    cursor.execute("""
        SELECT serial_start, serial_end, make, model
        FROM serial_ranges
    """)
    range_samples = cursor.fetchall()

    conn.close()

    return {
        'exact': exact_samples,
        'ranges': range_samples
    }


def generate_serial_in_range(start: str, end: str) -> str:
    """
    Generate a serial number that falls within a range.

    For simplicity, this will generate a number closer to the start.
    """
    # Find the common prefix
    prefix = ""
    for i in range(min(len(start), len(end))):
        if start[i] == end[i]:
            prefix += start[i]
        else:
            break

    # For testing, we'll use the start serial with a small increment
    # This is a simple approach - more sophisticated logic could be added
    if len(start) > len(prefix):
        # Try to increment the character after the prefix
        rest = start[len(prefix):]
        # Just return a serial close to start for testing
        return start[:-1] + '1' if start[-1] != 'Z' else start
    return start


def run_tests():
    """Run comprehensive lookup tests."""
    db_path = "drone_serials.db"

    if not Path(db_path).exists():
        print("Error: Database not found. Please run build_database.py first.")
        return

    print("=" * 70)
    print("DRONE SERIAL LOOKUP TEST SUITE")
    print("=" * 70)

    # Show database stats
    print("\nDatabase Statistics:")
    print("-" * 70)
    try:
        stats = get_database_stats(db_path)
        for key, value in stats.items():
            print(f"  {key}: {value}")
    except Exception as e:
        print(f"  Error getting stats: {e}")

    # Get test data
    print("\nLoading test data...")
    test_data = get_test_serials(db_path)

    # Test 1: Exact serial lookups (known)
    print("\n" + "=" * 70)
    print("TEST 1: Known Exact Serial Numbers")
    print("=" * 70)

    exact_tests = random.sample(test_data['exact'], min(5, len(test_data['exact'])))
    for i, (serial, make, model) in enumerate(exact_tests, 1):
        print(f"\nTest 1.{i}: {serial}")
        result = lookup_serial(serial, db_path)
        print(f"  Expected: {make} - {model}")
        print(f"  Found: {result['found']}")
        if result['found']:
            print(f"  Result: {result['make']} - {result['model']}")
            status = "✓ PASS" if result['make'] == make and result['model'] == model else "✗ FAIL"
            print(f"  Status: {status}")
        else:
            print(f"  Status: ✗ FAIL (not found)")

    # Test 2: Range-based lookups
    print("\n" + "=" * 70)
    print("TEST 2: Serial Numbers in Ranges")
    print("=" * 70)

    if test_data['ranges']:
        range_tests = random.sample(test_data['ranges'], min(3, len(test_data['ranges'])))
        for i, (start, end, make, model) in enumerate(range_tests, 1):
            # Test with start of range
            test_serial = start
            print(f"\nTest 2.{i}a: {test_serial} (start of range)")
            result = lookup_serial(test_serial, db_path)
            print(f"  Range: {start} to {end}")
            print(f"  Expected: {make} - {model}")
            print(f"  Found: {result['found']}")
            if result['found']:
                print(f"  Result: {result['make']} - {result['model']}")
                status = "✓ PASS" if result['make'] == make else "✗ FAIL"
                print(f"  Status: {status}")
            else:
                print(f"  Status: ✗ FAIL (not found)")

            # Test with end of range
            test_serial = end
            print(f"\nTest 2.{i}b: {test_serial} (end of range)")
            result = lookup_serial(test_serial, db_path)
            print(f"  Range: {start} to {end}")
            print(f"  Expected: {make} - {model}")
            print(f"  Found: {result['found']}")
            if result['found']:
                print(f"  Result: {result['make']} - {result['model']}")
                status = "✓ PASS" if result['make'] == make else "✗ FAIL"
                print(f"  Status: {status}")
            else:
                print(f"  Status: ✗ FAIL (not found)")
    else:
        print("\nNo range data found in database.")

    # Test 3: Unknown serials
    print("\n" + "=" * 70)
    print("TEST 3: Unknown Serial Numbers")
    print("=" * 70)

    unknown_serials = [
        "UNKNOWN123456789",
        "ZZZZZZZZZZZZZZZ",
        "0000000000000000",
        "NOTFOUND999",
        "INVALID_SERIAL"
    ]

    for i, serial in enumerate(unknown_serials, 1):
        print(f"\nTest 3.{i}: {serial}")
        result = lookup_serial(serial, db_path)
        print(f"  Found: {result['found']}")
        print(f"  Make: {result['make']}")
        print(f"  Model: {result['model']}")
        status = "✓ PASS" if not result['found'] else "✗ FAIL (should not be found)"
        print(f"  Status: {status}")

    # Test 4: Edge cases
    print("\n" + "=" * 70)
    print("TEST 4: Edge Cases")
    print("=" * 70)

    edge_cases = [
        ("", "Empty string"),
        ("   ", "Whitespace only"),
        ("  TRIM_TEST  ", "Serial with whitespace"),
    ]

    for i, (serial, description) in enumerate(edge_cases, 1):
        print(f"\nTest 4.{i}: {description}")
        print(f"  Input: '{serial}'")
        result = lookup_serial(serial, db_path)
        print(f"  Found: {result['found']}")
        print(f"  Status: ✓ PASS (handled without error)")

    # Test 5: JSON output format validation
    print("\n" + "=" * 70)
    print("TEST 5: JSON Output Format Validation")
    print("=" * 70)

    if test_data['exact']:
        test_serial = test_data['exact'][0][0]
        print(f"\nTesting JSON serialization with: {test_serial}")
        result = lookup_serial(test_serial, db_path)

        try:
            json_output = json.dumps(result, indent=2)
            print("\nJSON Output:")
            print(json_output)

            # Verify all required fields are present
            required_fields = ['found', 'serial_number', 'rid_tracking',
                             'description', 'status', 'make', 'model', 'mfr_serial']
            missing_fields = [f for f in required_fields if f not in result]

            if not missing_fields:
                print("\n  Status: ✓ PASS (all required fields present)")
            else:
                print(f"\n  Status: ✗ FAIL (missing fields: {missing_fields})")

        except Exception as e:
            print(f"\n  Status: ✗ FAIL (JSON serialization error: {e})")

    print("\n" + "=" * 70)
    print("TEST SUITE COMPLETE")
    print("=" * 70 + "\n")


if __name__ == "__main__":
    run_tests()
