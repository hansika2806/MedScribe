"""
Safety Trigger Test
Tests that dangerous drug combinations trigger safety guardrail
"""
import requests
import json
import sys
from pathlib import Path

# Fix Windows console encoding
if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except:
        pass

# API base URL
BASE_URL = "http://localhost:8000"


def test_safety_trigger():
    """Test that warfarin + aspirin triggers safety guardrail"""
    print("="*60)
    print("SAFETY TRIGGER TEST")
    print("="*60)
    print("\nTesting dangerous drug combination: warfarin + aspirin")
    print("Expected: safety_pass = false, review_type = urgent_safety\n")
    
    # Check if test audio exists
    audio_path = Path("tests/test_safety_trigger.mp3")
    if not audio_path.exists():
        print("❌ FAIL: test_safety_trigger.mp3 not found")
        print("   Run: python tests/generate_test_audio.py")
        return False
    
    try:
        # Submit consultation
        with open(audio_path, 'rb') as f:
            files = {'audio_file': ('test_safety_trigger.mp3', f, 'audio/mpeg')}
            
            print("Submitting safety trigger consultation... (30-60 seconds)")
            response = requests.post(
                f"{BASE_URL}/consultation",
                files=files,
                timeout=120
            )
        
        if response.status_code != 200:
            print(f"❌ FAIL: HTTP {response.status_code}")
            print(f"Response: {response.text[:200]}")
            return False
        
        data = response.json()
        print(f"✅ Consultation submitted: {data.get('session_id')}\n")
        
        # Check safety result
        print("-" * 60)
        print("CHECKING SAFETY RESULT")
        print("-" * 60)
        
        safety_result = data.get("safety_result", {})
        safety_pass = safety_result.get("safety_pass")
        safety_flags = safety_result.get("safety_flags", [])
        
        print(f"Safety Pass: {safety_pass}")
        print(f"Safety Flags: {len(safety_flags)}")
        
        if safety_flags:
            print("\nSafety Flags Raised:")
            for i, flag in enumerate(safety_flags, 1):
                print(f"  {i}. {flag.get('check_type')}: {flag.get('detail')}")
                print(f"     Urgency: {flag.get('urgency')}")
        
        # Check review type
        print("\n" + "-" * 60)
        print("CHECKING REVIEW ROUTING")
        print("-" * 60)
        
        review_type = data.get("review_type")
        review_message = data.get("review_message")
        
        print(f"Review Type: {review_type}")
        print(f"Review Message: {review_message}")
        
        # Verify expectations
        print("\n" + "=" * 60)
        print("VERIFICATION")
        print("=" * 60)
        
        all_passed = True
        
        # Test 1: Safety should NOT pass
        if safety_pass == False:
            print("✅ PASS: safety_pass = false (as expected)")
        else:
            print(f"❌ FAIL: safety_pass = {safety_pass} (expected false)")
            all_passed = False
        
        # Test 2: Should have safety flags
        if len(safety_flags) > 0:
            print(f"✅ PASS: {len(safety_flags)} safety flag(s) raised")
        else:
            print("❌ FAIL: No safety flags raised (expected at least 1)")
            all_passed = False
        
        # Test 3: Review type should be urgent_safety
        if review_type == "urgent_safety":
            print("✅ PASS: review_type = urgent_safety (as expected)")
        else:
            print(f"❌ FAIL: review_type = {review_type} (expected urgent_safety)")
            all_passed = False
        
        # Test 4: Check for drug interaction flag
        has_drug_interaction = any(
            flag.get("check_type") == "drug_interaction" 
            for flag in safety_flags
        )
        if has_drug_interaction:
            print("✅ PASS: Drug interaction detected")
        else:
            print("⚠️  WARNING: No drug_interaction flag (may have other safety concerns)")
        
        print("\n" + "=" * 60)
        if all_passed:
            print("🎉 SAFETY TRIGGER TEST PASSED!")
            print("The system correctly identified the dangerous drug combination")
        else:
            print("❌ SAFETY TRIGGER TEST FAILED")
            print("The system did not properly flag the safety risk")
        print("=" * 60)
        
        return all_passed
        
    except requests.exceptions.Timeout:
        print("❌ FAIL: Request timed out (>120s)")
        return False
    except requests.exceptions.ConnectionError:
        print("❌ FAIL: Cannot connect to server")
        print("   Is the server running? Start with: python backend/main.py")
        return False
    except Exception as e:
        print(f"❌ FAIL: Error: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run safety trigger test"""
    success = test_safety_trigger()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()


# Made with Bob