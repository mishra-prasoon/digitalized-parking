"""
Test ANPR without a real camera.
Simulates what ANPR would do by directly calling the API.
"""
import requests

API_BASE = 'http://127.0.0.1:8000/api'

def simulate_entry(plate_number):
    print(f"\n🚗 Vehicle arriving at ENTRY gate: {plate_number}")
    response = requests.post(f'{API_BASE}/entry/', json={'plate_number': plate_number})
    print(f"Response: {response.json()}")
    return response.json()

def simulate_exit(plate_number):
    print(f"\n🚗 Vehicle leaving at EXIT gate: {plate_number}")
    response = requests.post(f'{API_BASE}/exit/', json={'plate_number': plate_number})
    print(f"Response: {response.json()}")
    return response.json()

def check_parking_status():
    print(f"\n📊 Current parking status:")
    response = requests.get(f'{API_BASE}/active/')
    data = response.json()
    print(f"Currently parked: {data['currently_parked']}")

    slots = requests.get(f'{API_BASE}/slots/available/')
    slot_data = slots.json()
    print(f"Available slots: {slot_data['total_available']}")

if __name__ == '__main__':
    print("="*50)
    print("ANPR SIMULATION TEST")
    print("="*50)

    # Test 1: Multiple vehicles entering
    simulate_entry("MH12AB3456")
    simulate_entry("DL01CD7890")
    simulate_entry("UP32XY1111")
    check_parking_status()

    # Test 2: One vehicle exits
    simulate_exit("MH12AB3456")
    check_parking_status()

    # Test 3: Duplicate entry attempt
    simulate_entry("DL01CD7890")  # Should reject

    print("\n✅ ANPR simulation test complete!")