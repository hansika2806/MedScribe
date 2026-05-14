"""
Generate test audio files for Phase 2 testing using gTTS
"""
import os
import sys
from pathlib import Path

# Fix Windows console encoding
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

try:
    from gtts import gTTS
    GTTS_AVAILABLE = True
except ImportError:
    GTTS_AVAILABLE = False
    print("WARNING: gTTS not installed. Install with: pip install gtts")

# Test audio directory
TEST_DIR = Path(__file__).parent
TEST_DIR.mkdir(exist_ok=True)


def generate_diabetes_consultation():
    """
    Generate test audio for diabetes consultation
    Includes: diabetes, hypertension, metformin, lisinopril
    """
    if not GTTS_AVAILABLE:
        print("❌ Cannot generate audio - gTTS not available")
        return False
    
    print("🎤 Generating diabetes consultation audio...")
    
    # Realistic consultation dialogue
    dialogue = """
    Doctor: Good morning. How are you feeling today?
    Patient: Not great doctor. I've been feeling very tired lately and I'm always thirsty.
    Doctor: I see. How long have you been experiencing these symptoms?
    Patient: About three months now. And I've been urinating more frequently too.
    Doctor: Okay. Let me check your blood pressure. Your blood pressure is 158 over 96. That's elevated.
    Patient: Is that bad?
    Doctor: It's higher than we'd like. Let me also check your blood sugar. Your fasting glucose is 185.
    Patient: What does that mean?
    Doctor: Based on your symptoms and test results, you have type 2 diabetes and hypertension.
    Patient: Oh no. What do we do?
    Doctor: We'll start you on metformin 500 milligrams twice daily with meals for the diabetes.
    Patient: Okay.
    Doctor: And I'm prescribing lisinopril 10 milligrams once daily for your blood pressure.
    Patient: Will this help?
    Doctor: Yes. These medications will help control your blood sugar and blood pressure. 
    You'll also need to make lifestyle changes - diet and exercise.
    Patient: I understand.
    Doctor: Come back in two weeks for a follow-up. We'll check your progress.
    Patient: Thank you doctor.
    """
    
    try:
        # Generate audio
        tts = gTTS(text=dialogue, lang='en', slow=False)
        output_path = TEST_DIR / "test_consultation.mp3"
        tts.save(str(output_path))
        
        print(f"✅ Generated: {output_path}")
        print(f"   Size: {output_path.stat().st_size} bytes")
        return True
        
    except Exception as e:
        print(f"❌ Failed to generate audio: {e}")
        return False


def generate_safety_trigger_consultation():
    """
    Generate test audio with drug interaction (warfarin + aspirin)
    Should trigger safety guardrail
    """
    if not GTTS_AVAILABLE:
        print("❌ Cannot generate audio - gTTS not available")
        return False
    
    print("🎤 Generating safety trigger consultation audio...")
    
    # Dialogue with dangerous drug combination
    dialogue = """
    Doctor: Hello. What brings you in today?
    Patient: I've been having chest pain doctor.
    Doctor: I see. Are you currently taking any medications?
    Patient: Yes, I'm taking warfarin for my heart.
    Doctor: Okay. Let me examine you. Your blood pressure is 145 over 88.
    Patient: Is that okay?
    Doctor: It's slightly elevated. For the chest pain, I'm going to prescribe aspirin 325 milligrams daily.
    Patient: Aspirin? Is that safe with my warfarin?
    Doctor: Yes, we'll monitor you closely. Take both medications as prescribed.
    Patient: Okay doctor.
    Doctor: Come back if the chest pain worsens.
    """
    
    try:
        # Generate audio
        tts = gTTS(text=dialogue, lang='en', slow=False)
        output_path = TEST_DIR / "test_safety_trigger.mp3"
        tts.save(str(output_path))
        
        print(f"✅ Generated: {output_path}")
        print(f"   Size: {output_path.stat().st_size} bytes")
        return True
        
    except Exception as e:
        print(f"❌ Failed to generate audio: {e}")
        return False


if __name__ == "__main__":
    print("=" * 60)
    print("Phase 2 Test Audio Generation")
    print("=" * 60)
    
    if not GTTS_AVAILABLE:
        print("\n⚠️ gTTS not installed!")
        print("Install with: pip install gtts")
        exit(1)
    
    print("\nGenerating test audio files...\n")
    
    # Generate both test files
    success1 = generate_diabetes_consultation()
    print()
    success2 = generate_safety_trigger_consultation()
    
    print("\n" + "=" * 60)
    if success1 and success2:
        print("✅ All test audio files generated successfully!")
        print("\nGenerated files:")
        print("  - tests/test_consultation.mp3 (diabetes consultation)")
        print("  - tests/test_safety_trigger.mp3 (safety trigger)")
    else:
        print("❌ Some audio files failed to generate")
        exit(1)
    print("=" * 60)


# Made with Bob
