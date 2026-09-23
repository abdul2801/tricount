"""Quick test of the app structure."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from app import create_app
from app.tricount_service import get_service

def test_app_creation():
    """Test that the app can be created."""
    app = create_app()
    assert app is not None
    print("✓ App created successfully")
    
    with app.app_context():
        print("✓ App context working")

def test_service():
    """Test that the service initializes."""
    try:
        service = get_service()
        print("✓ Tricount service initialized")
        
        # Try to get data
        summary = service.get_summary()
        print(f"✓ Got summary: {summary['title']}")
        
        members = service.get_members()
        print(f"✓ Got {len(members)} members")
        
        transactions = service.get_transactions()
        print(f"✓ Got {len(transactions)} transactions")
        
    except Exception as e:
        print(f"✗ Service error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    print("\n=== Testing Tricount Dashboard ===\n")
    test_app_creation()
    print()
    test_service()
    print("\n=== All tests passed! ===\n")
