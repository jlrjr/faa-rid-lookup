#!/usr/bin/env python3
"""
Example usage of the drone_serial_lookup module.

This demonstrates how to integrate the lookup functionality into
WarDragon/DragonSync workflows.
"""

import json
from drone_serial_lookup import lookup_serial, get_database_stats


def example_basic_lookup():
    """Basic lookup example."""
    print("=" * 70)
    print("EXAMPLE 1: Basic Serial Number Lookup")
    print("=" * 70)

    serial = "2146BF3300000000"
    result = lookup_serial(serial)

    print(f"\nLooking up serial: {serial}")
    print(f"Found: {result['found']}")

    if result['found']:
        print(f"Manufacturer: {result['make']}")
        print(f"Model: {result['model']}")
        print(f"RID Tracking: {result['rid_tracking']}")
        print(f"Status: {result['status']}")


def example_range_lookup():
    """Example of looking up a serial in a range."""
    print("\n" + "=" * 70)
    print("EXAMPLE 2: Range-Based Lookup (DJI)")
    print("=" * 70)

    serial = "1581F5BK000000000001"
    result = lookup_serial(serial)

    print(f"\nLooking up serial: {serial}")
    print(f"Found: {result['found']}")

    if result['found']:
        print(f"Manufacturer: {result['make']}")
        print(f"Model: {result['model']}")


def example_unknown_drone():
    """Example of handling unknown drones."""
    print("\n" + "=" * 70)
    print("EXAMPLE 3: Handling Unknown Drones")
    print("=" * 70)

    serial = "UNKNOWN123456"
    result = lookup_serial(serial)

    print(f"\nLooking up serial: {serial}")
    print(f"Found: {result['found']}")

    if not result['found']:
        print("This drone is not in the FAA Remote ID database.")
        print("It may be:")
        print("  - A non-compliant drone")
        print("  - A newly registered drone not yet in our data")
        print("  - An invalid serial number")


def example_batch_lookup():
    """Example of looking up multiple serials."""
    print("\n" + "=" * 70)
    print("EXAMPLE 4: Batch Lookup")
    print("=" * 70)

    serials = [
        "2146BF3300000000",    # Contixo F33
        "1581F5BK000000000001", # DJI M30T
        "UNKNOWN123",          # Unknown
        "1869AU11S000021"      # Ruko U11S
    ]

    results = []
    for serial in serials:
        result = lookup_serial(serial)
        results.append(result)
        status = "✓" if result['found'] else "✗"
        make_model = f"{result['make']} {result['model']}" if result['found'] else "Not found"
        print(f"{status} {serial}: {make_model}")

    return results


def example_json_export():
    """Example of exporting results as JSON."""
    print("\n" + "=" * 70)
    print("EXAMPLE 5: JSON Export for Integration")
    print("=" * 70)

    serial = "2146BF3300000000"
    result = lookup_serial(serial)

    # Convert to JSON for API/sink integration
    json_output = json.dumps(result, indent=2)

    print(f"\nJSON output for serial {serial}:")
    print(json_output)

    # Example: Prepare for CoT/Lattice integration
    if result['found']:
        cot_data = {
            "type": "drone",
            "uid": f"DRONE-{serial}",
            "manufacturer": result['make'],
            "model": result['model'],
            "faa_rid": result['rid_tracking'],
            "compliance_status": result['status']
        }
        print("\nExample CoT/Lattice properties:")
        print(json.dumps(cot_data, indent=2))


def example_database_stats():
    """Example of getting database statistics."""
    print("\n" + "=" * 70)
    print("EXAMPLE 6: Database Statistics")
    print("=" * 70)

    stats = get_database_stats()

    print("\nDatabase Information:")
    for key, value in stats.items():
        print(f"  {key}: {value}")


def example_wardragon_integration():
    """
    Example showing how this could integrate with WarDragon workflow.

    This is a pseudo-code example showing the integration pattern.
    """
    print("\n" + "=" * 70)
    print("EXAMPLE 7: WarDragon/DragonSync Integration Pattern")
    print("=" * 70)

    print("""
# Pseudo-code for WarDragon integration:

from drone_serial_lookup import lookup_serial

def process_drone_detection(drone_id_packet):
    '''Process a DroneID packet and enrich with FAA data.'''

    # Extract serial from DroneID packet
    serial_number = drone_id_packet.get('serial_number')

    # Look up in FAA database
    faa_data = lookup_serial(serial_number)

    # Enrich the detection with FAA data
    enriched_data = {
        **drone_id_packet,
        'faa_found': faa_data['found'],
        'manufacturer': faa_data['make'],
        'model': faa_data['model'],
        'faa_rid': faa_data['rid_tracking'],
        'compliance_status': faa_data['status']
    }

    # Send to DragonSync sinks
    send_to_cot(enriched_data)
    send_to_lattice(enriched_data)

    return enriched_data

# Example usage
drone_packet = {
    'serial_number': '1581F5BK000000000001',
    'latitude': 37.7749,
    'longitude': -122.4194,
    'altitude': 100,
    'timestamp': '2025-11-25T16:54:00Z'
}

result = process_drone_detection(drone_packet)
    """)

    # Show actual example with real lookup
    print("\nActual lookup demonstration:")
    serial = "1581F5BK000000000001"
    faa_data = lookup_serial(serial)

    enriched = {
        'serial_number': serial,
        'latitude': 37.7749,
        'longitude': -122.4194,
        'altitude': 100,
        'faa_found': faa_data['found'],
        'manufacturer': faa_data['make'],
        'model': faa_data['model'],
        'faa_rid': faa_data['rid_tracking']
    }

    print(json.dumps(enriched, indent=2))


def main():
    """Run all examples."""
    example_basic_lookup()
    example_range_lookup()
    example_unknown_drone()
    example_batch_lookup()
    example_json_export()
    example_database_stats()
    example_wardragon_integration()

    print("\n" + "=" * 70)
    print("All examples completed!")
    print("=" * 70 + "\n")


if __name__ == "__main__":
    main()
