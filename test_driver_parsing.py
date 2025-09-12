"""
Test script to demonstrate driver parsing functionality.
This shows how the agent can parse various driver registration formats.
"""

from tools.llm_parser import get_parser
from tools.database_tools import register_driver

def test_driver_parsing():
    """Test driver parsing with various input formats."""
    
    print("🚛 Driver Parsing Test\n")
    
    # Test cases with different formats
    test_cases = [
        "I am John Doe, phone 9876543210, license DL1234567890",
        "Register driver Mike Smith with license DL987654321 and phone 9876543211",
        "Driver: Sarah Johnson, License: DL555666777, Contact: 9876543212",
        "My name is Alex Brown, DL123456789, phone 9876543213",
        "Driver registration - Name: Emma Wilson, License: DL999888777, Phone: 9876543214",
        "I'm Tom Davis, license DL111222333, contact 9876543215",
        "Driver info: Lisa Garcia, DL444555666, phone 9876543216",
        "Register me as driver: David Lee, license DL777888999, phone 9876543217"
    ]
    
    parser = get_parser()
    
    for i, test_input in enumerate(test_cases, 1):
        print(f"Test {i}: {test_input}")
        print("-" * 60)
        
        try:
            # Parse the input
            parsed_data = parser.parse_driver(test_input)
            print(f"✅ Parsed data: {parsed_data}")
            
            # Try to register the driver
            if parsed_data.get('name') and parsed_data['name'] != 'Unknown Driver':
                result = register_driver(parsed_data)
                print(f"📝 Registration result: {result}")
            else:
                print("⚠️ Skipping registration - no valid name found")
            
        except Exception as e:
            print(f"❌ Error: {e}")
        
        print()
    
    print("🎯 Driver parsing test completed!")
    print("\nKey Features Demonstrated:")
    print("• Flexible name extraction")
    print("• Phone number recognition")
    print("• License number parsing (various formats)")
    print("• Database registration")
    print("• Error handling and debugging")

if __name__ == "__main__":
    test_driver_parsing()
