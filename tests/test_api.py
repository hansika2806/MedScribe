"""
Test the MedScribe API endpoint

This script tests the /api/consultation endpoint with a test audio file.

Run with: python tests/test_api.py
"""

import sys
from pathlib import Path
import logging
import json
import time

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def test_api():
    """Test the consultation API endpoint"""
    try:
        import requests
    except ImportError:
        logger.error("requests library not installed")
        logger.error("Install with: pip install requests")
        return False
    
    # Check if test audio exists
    test_audio = Path(__file__).parent / "test_consultation.wav"
    
    if not test_audio.exists():
        logger.error(f"Test audio file not found: {test_audio}")
        logger.error("Generate it first with: python tests/generate_test_audio.py")
        return False
    
    logger.info("=" * 80)
    logger.info("MEDSCRIBE API TEST")
    logger.info("=" * 80)
    
    # API endpoint
    url = "http://localhost:8000/api/consultation"
    
    logger.info(f"\nTest audio: {test_audio}")
    logger.info(f"API endpoint: {url}")
    logger.info(f"Audio size: {test_audio.stat().st_size / 1024:.1f} KB")
    
    # Check if server is running
    try:
        health_response = requests.get("http://localhost:8000/health", timeout=2)
        if health_response.status_code != 200:
            logger.error("Server is not healthy")
            return False
        logger.info("✅ Server is running")
    except requests.exceptions.RequestException:
        logger.error("❌ Server is not running")
        logger.error("Start the server with: python backend/main.py")
        return False
    
    # Send request
    logger.info("\nSending consultation request...")
    logger.info("(This may take 30-60 seconds for first run while models load)")
    
    start_time = time.time()
    
    try:
        with open(test_audio, 'rb') as f:
            files = {'audio_file': ('test_consultation.wav', f, 'audio/wav')}
            response = requests.post(url, files=files, timeout=300)
        
        elapsed = time.time() - start_time
        
        if response.status_code != 200:
            logger.error(f"❌ Request failed with status {response.status_code}")
            logger.error(f"Response: {response.text}")
            return False
        
        # Parse response
        result = response.json()
        
        logger.info(f"\n✅ Request successful!")
        logger.info(f"Processing time: {elapsed:.1f} seconds")
        
        # Display results
        logger.info("\n" + "=" * 80)
        logger.info("SOAP NOTE RESULT")
        logger.info("=" * 80)
        
        soap = result.get('soap_note', {})
        
        # Subjective
        logger.info("\n[SUBJECTIVE]")
        logger.info(f"Confidence: {soap.get('subjective', {}).get('confidence', 0):.2f}")
        logger.info(soap.get('subjective', {}).get('content', 'N/A'))
        
        # Objective
        logger.info("\n[OBJECTIVE]")
        logger.info(f"Confidence: {soap.get('objective', {}).get('confidence', 0):.2f}")
        logger.info(soap.get('objective', {}).get('content', 'N/A'))
        
        # Assessment
        logger.info("\n[ASSESSMENT]")
        logger.info(f"Confidence: {soap.get('assessment', {}).get('confidence', 0):.2f}")
        logger.info(soap.get('assessment', {}).get('content', 'N/A'))
        
        # Plan
        logger.info("\n[PLAN]")
        logger.info(f"Confidence: {soap.get('plan', {}).get('confidence', 0):.2f}")
        logger.info(soap.get('plan', {}).get('content', 'N/A'))
        
        # Quality checks
        logger.info("\n" + "=" * 80)
        logger.info("QUALITY CHECKS")
        logger.info("=" * 80)
        
        checks = []
        
        # Check 1: All sections present
        sections = ['subjective', 'objective', 'assessment', 'plan']
        all_present = all(soap.get(s, {}).get('content') for s in sections)
        checks.append(("All SOAP sections present", all_present))
        
        # Check 2: Confidence scores reasonable
        confidences = [soap.get(s, {}).get('confidence', 0) for s in sections]
        avg_confidence = sum(confidences) / len(confidences) if confidences else 0
        checks.append(("Average confidence >= 0.70", avg_confidence >= 0.70))
        
        # Check 3: Provenance present
        has_provenance = any(
            soap.get(s, {}).get('entities') 
            for s in sections
        )
        checks.append(("Entity provenance present", has_provenance))
        
        # Check 4: Processing time reasonable
        checks.append(("Processing time < 120s", elapsed < 120))
        
        # Display checks
        for check_name, passed in checks:
            status = "✅" if passed else "❌"
            logger.info(f"{status} {check_name}")
        
        # Summary
        passed_count = sum(1 for _, p in checks if p)
        total_count = len(checks)
        
        logger.info(f"\nQuality Score: {passed_count}/{total_count} checks passed")
        
        # Save full response
        output_file = Path(__file__).parent / "test_result.json"
        with open(output_file, 'w') as f:
            json.dump(result, f, indent=2)
        logger.info(f"\nFull response saved to: {output_file}")
        
        return passed_count == total_count
        
    except requests.exceptions.Timeout:
        logger.error("❌ Request timed out (>300s)")
        logger.error("The models may be taking too long to load or process")
        return False
    except Exception as e:
        logger.error(f"❌ Request failed: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False


def main():
    """Main function"""
    success = test_api()
    
    if success:
        logger.info("\n" + "=" * 80)
        logger.info("🎉 ALL CHECKS PASSED!")
        logger.info("=" * 80)
        logger.info("\nPhase 1 MVP is working correctly.")
        logger.info("Next: Implement Phase 2 (RAG, Guardrails, Routing)")
    else:
        logger.error("\n" + "=" * 80)
        logger.error("❌ SOME CHECKS FAILED")
        logger.error("=" * 80)
        logger.error("\nReview the errors above and fix before proceeding.")
    
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())

# Made with Bob
