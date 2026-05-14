"""
Comprehensive Phase 2 Test Suite
Tests all Phase 2 features: RAG, ICD-10, QA, Safety, Routing, Metrics
"""
import requests
import json
import sys
from pathlib import Path
from typing import Dict, Any, List

# Fix Windows console encoding
if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except:
        pass

# API base URL
BASE_URL = "http://localhost:8000"

# Test results tracking
test_results = []


def log_test(name: str, passed: bool, details: str = ""):
    """Log test result"""
    status = "✅ PASS" if passed else "❌ FAIL"
    test_results.append({
        "name": name,
        "passed": passed,
        "details": details
    })
    print(f"{status}: {name}")
    if details:
        print(f"   {details}")


def test_health_check() -> bool:
    """Test 1: Health check endpoint"""
    print("\n" + "="*60)
    print("TEST 1: Health Check")
    print("="*60)
    
    try:
        response = requests.get(f"{BASE_URL}/health", timeout=5)
        
        if response.status_code == 200:
            data = response.json()
            if data.get("status") == "healthy":
                log_test("Health Check", True, f"Version: {data.get('version')}")
                return True
            else:
                log_test("Health Check", False, f"Unexpected status: {data.get('status')}")
                return False
        else:
            log_test("Health Check", False, f"Status code: {response.status_code}")
            return False
            
    except requests.exceptions.ConnectionError:
        log_test("Health Check", False, "Cannot connect to server. Is it running?")
        return False
    except Exception as e:
        log_test("Health Check", False, f"Error: {str(e)}")
        return False


def test_consultation_submission() -> Dict[str, Any] | None:
    """Test 2: Submit consultation and get SOAP note"""
    print("\n" + "="*60)
    print("TEST 2: Consultation Submission")
    print("="*60)
    
    # Check if test audio exists
    audio_path = Path("tests/test_consultation.mp3")
    if not audio_path.exists():
        log_test("Consultation Submission", False, "test_consultation.mp3 not found")
        return None
    
    try:
        # Submit consultation
        with open(audio_path, 'rb') as f:
            files = {'audio_file': ('test_consultation.mp3', f, 'audio/mpeg')}
            
            print("Submitting consultation... (this may take 30-60 seconds)")
            response = requests.post(
                f"{BASE_URL}/consultation",
                files=files,
                timeout=300
            )
        
        if response.status_code == 200:
            data = response.json()
            log_test("Consultation Submission", True, f"Session ID: {data.get('session_id')}")
            return data
        else:
            log_test("Consultation Submission", False, f"Status code: {response.status_code}, Response: {response.text[:200]}")
            return None
            
    except requests.exceptions.Timeout:
        log_test("Consultation Submission", False, "Request timed out (>300s)")
        return None
    except Exception as e:
        log_test("Consultation Submission", False, f"Error: {str(e)}")
        return None


def test_retrieved_guidelines(response_data: Dict[str, Any]) -> bool:
    """Test 3: Verify retrieved guidelines"""
    print("\n" + "="*60)
    print("TEST 3: Retrieved Guidelines")
    print("="*60)
    
    guidelines = response_data.get("retrieved_guidelines", [])
    
    if not guidelines:
        log_test("Retrieved Guidelines - Non-empty", False, "No guidelines retrieved")
        return False
    
    log_test("Retrieved Guidelines - Non-empty", True, f"Retrieved {len(guidelines)} guidelines")
    
    # Check guideline structure
    first_guideline = guidelines[0]
    required_fields = ["content", "source", "relevance_score", "population_match"]
    
    missing_fields = [f for f in required_fields if f not in first_guideline]
    if missing_fields:
        log_test("Retrieved Guidelines - Structure", False, f"Missing fields: {missing_fields}")
        return False
    
    log_test("Retrieved Guidelines - Structure", True, f"Source: {first_guideline['source']}, Score: {first_guideline['relevance_score']}")
    
    return True


def test_icd10_codes(response_data: Dict[str, Any]) -> bool:
    """Test 4: Verify ICD-10 codes"""
    print("\n" + "="*60)
    print("TEST 4: ICD-10 Codes")
    print("="*60)
    
    # Check if soap_note exists
    soap_note = response_data.get("soap_note")
    if not soap_note:
        log_test("ICD-10 Codes", False, "No SOAP note in response")
        return False
    
    # Check assessment content for ICD-10 codes
    assessment = soap_note.get("assessment", {})
    content = assessment.get("content", "")
    
    has_icd10 = "ICD-10:" in content or "ICD-10" in content
    
    if has_icd10:
        # Extract ICD-10 code
        import re
        icd_match = re.search(r'ICD-10:\s*([A-Z]\d+\.?\d*)', content)
        if icd_match:
            code = icd_match.group(1)
            log_test("ICD-10 Codes - Present", True, f"Found code: {code}")
            
            # Check if it's not PENDING
            if code != "PENDING":
                log_test("ICD-10 Codes - Not PENDING", True, f"Valid code: {code}")
                return True
            else:
                log_test("ICD-10 Codes - Not PENDING", False, "Code is PENDING")
                return False
        else:
            log_test("ICD-10 Codes - Present", True, "ICD-10 mentioned but code not extracted")
            return True
    else:
        log_test("ICD-10 Codes - Present", False, "No ICD-10 codes found in assessment")
        return False


def test_qa_result(response_data: Dict[str, Any]) -> bool:
    """Test 5: Verify QA result"""
    print("\n" + "="*60)
    print("TEST 5: QA Result")
    print("="*60)
    
    qa_result = response_data.get("qa_result")
    
    if not qa_result:
        log_test("QA Result - Present", False, "No qa_result in response")
        return False
    
    log_test("QA Result - Present", True)
    
    # Check for required fields
    if "pass" not in qa_result:
        log_test("QA Result - Has 'pass' field", False, "Missing 'pass' field")
        return False
    
    log_test("QA Result - Has 'pass' field", True, f"Pass: {qa_result['pass']}")
    
    # Check confidence
    confidence = qa_result.get("overall_confidence", 0)
    log_test("QA Result - Confidence", True, f"Overall confidence: {confidence:.2f}")
    
    # Check flags
    flags = qa_result.get("flags", [])
    log_test("QA Result - Flags", True, f"{len(flags)} flags raised")
    
    return True


def test_safety_result(response_data: Dict[str, Any]) -> bool:
    """Test 6: Verify safety result"""
    print("\n" + "="*60)
    print("TEST 6: Safety Result")
    print("="*60)
    
    safety_result = response_data.get("safety_result")
    
    if not safety_result:
        log_test("Safety Result - Present", False, "No safety_result in response")
        return False
    
    log_test("Safety Result - Present", True)
    
    # Check for required fields
    if "safety_pass" not in safety_result:
        log_test("Safety Result - Has 'safety_pass' field", False, "Missing 'safety_pass' field")
        return False
    
    safety_pass = safety_result["safety_pass"]
    log_test("Safety Result - Has 'safety_pass' field", True, f"Safety pass: {safety_pass}")
    
    # Check flags
    flags = safety_result.get("safety_flags", [])
    log_test("Safety Result - Flags", True, f"{len(flags)} safety flags raised")
    
    return True


def test_review_fields(response_data: Dict[str, Any]) -> bool:
    """Test 7: Verify review routing fields"""
    print("\n" + "="*60)
    print("TEST 7: Review Routing Fields")
    print("="*60)
    
    required_fields = ["review_type", "requires_physician_review", "review_message"]
    
    all_present = True
    for field in required_fields:
        if field not in response_data:
            log_test(f"Review Field - {field}", False, "Field missing")
            all_present = False
        else:
            value = response_data[field]
            log_test(f"Review Field - {field}", True, f"Value: {value}")
    
    return all_present


def test_diarization_method(response_data: Dict[str, Any]) -> bool:
    """Test 8: Verify diarization method field"""
    print("\n" + "="*60)
    print("TEST 8: Diarization Method")
    print("="*60)
    
    method = response_data.get("diarization_method")
    
    if not method:
        log_test("Diarization Method", False, "Field missing")
        return False
    
    valid_methods = ["speechbrain", "fallback", "pyannote"]
    if method in valid_methods:
        log_test("Diarization Method", True, f"Method: {method}")
        return True
    else:
        log_test("Diarization Method", False, f"Invalid method: {method}")
        return False


def test_metrics_endpoint() -> bool:
    """Test 9: Verify metrics endpoint"""
    print("\n" + "="*60)
    print("TEST 9: Metrics Endpoint")
    print("="*60)
    
    try:
        response = requests.get(f"{BASE_URL}/metrics", timeout=5)
        
        if response.status_code == 200:
            data = response.json()
            metrics = data.get("metrics", {})
            
            total = metrics.get("total_consultations", 0)
            if total >= 1:
                log_test("Metrics - Total Consultations", True, f"Total: {total}")
            else:
                log_test("Metrics - Total Consultations", False, f"Expected >= 1, got {total}")
                return False
            
            # Check other metrics
            log_test("Metrics - Success Rate", True, f"Successful: {metrics.get('successful_completions', 0)}")
            log_test("Metrics - Avg Processing Time", True, f"{metrics.get('average_processing_time', 0):.2f}s")
            
            return True
        else:
            log_test("Metrics Endpoint", False, f"Status code: {response.status_code}")
            return False
            
    except Exception as e:
        log_test("Metrics Endpoint", False, f"Error: {str(e)}")
        return False


def print_summary():
    """Print test summary"""
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)
    
    passed = [t for t in test_results if t["passed"]]
    failed = [t for t in test_results if not t["passed"]]
    
    print(f"\nTotal Tests: {len(test_results)}")
    print(f"✅ Passed: {len(passed)}")
    print(f"❌ Failed: {len(failed)}")
    
    if failed:
        print("\nFailed Tests:")
        for test in failed:
            print(f"  - {test['name']}")
            if test['details']:
                print(f"    {test['details']}")
    
    print("\n" + "="*60)
    
    if len(failed) == 0:
        print("🎉 ALL TESTS PASSED!")
    else:
        print(f"⚠️ {len(failed)} TEST(S) FAILED")
    print("="*60)
    
    return len(failed) == 0


def main():
    """Run all Phase 2 tests"""
    print("="*60)
    print("PHASE 2 COMPREHENSIVE TEST SUITE")
    print("="*60)
    print("\nTesting MedScribe Phase 2 Features:")
    print("  - RAG with clinical guidelines")
    print("  - ICD-10 coding")
    print("  - QA guardrails")
    print("  - Safety guardrails")
    print("  - Routing logic")
    print("  - Metrics tracking")
    
    # Test 1: Health check
    if not test_health_check():
        print("\n❌ Server not responding. Please start the server first:")
        print("   python backend/main.py")
        return False
    
    # Test 2: Submit consultation
    response_data = test_consultation_submission()
    if not response_data:
        print("\n❌ Consultation submission failed. Cannot continue tests.")
        return False
    
    # Tests 3-8: Verify response structure
    test_retrieved_guidelines(response_data)
    test_icd10_codes(response_data)
    test_qa_result(response_data)
    test_safety_result(response_data)
    test_review_fields(response_data)
    test_diarization_method(response_data)
    
    # Test 9: Metrics
    test_metrics_endpoint()
    
    # Print summary
    all_passed = print_summary()
    
    return all_passed


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)


# Made with Bob
