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
AUDIO_DIR = TEST_DIR / "audio"
AUDIO_DIR.mkdir(exist_ok=True)


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


SPECIALTY_SCRIPTS = {
    "cardiology_consultation.mp3": """
    Doctor: Good morning. What brings you in today?
    Patient: Doctor I have been having chest pain for the past two days. It feels like pressure on my chest.
    Doctor: Does the pain radiate anywhere?
    Patient: Yes it goes to my left arm sometimes.
    Doctor: Any shortness of breath or sweating?
    Patient: Yes both. Especially when I climb stairs.
    Doctor: How old are you and do you smoke?
    Patient: I am 58 years old. I smoked for 20 years but stopped 5 years ago.
    Doctor: Your blood pressure is 162 over 98. Heart rate is 92. I can see from your ECG there are some ST segment changes.
    Patient: Is it serious doctor?
    Doctor: We need to rule out a cardiac event. Your troponin levels are slightly elevated at 0.02. I am going to start you on aspirin 325 milligrams immediately and refer you to cardiology urgently.
    Patient: My father also had a heart attack at 60.
    Doctor: That is important information. We will do a complete cardiac workup.
    """,
    "endocrinology_consultation.mp3": """
    Doctor: Hello. How have you been feeling since your last visit?
    Patient: Not well doctor. I am always tired and thirsty. I drink water constantly.
    Doctor: How long has this been going on?
    Patient: About 3 months. I also gained 5 kilograms.
    Doctor: Any frequent urination especially at night?
    Patient: Yes every 2 to 3 hours at night.
    Doctor: Your HbA1c has come back at 9.8 percent which is quite high. Fasting glucose is 245.
    Patient: That is worse than last time.
    Doctor: Yes. I also see your TSH is 8.5 which suggests your thyroid is underactive.
    Patient: I did not know I had thyroid problems.
    Doctor: We will start levothyroxine 50 micrograms once daily and increase your metformin to 1000 milligrams twice daily. You also need to see a dietician for meal planning.
    Patient: My mother also had diabetes and thyroid.
    """,
    "pediatrics_consultation.mp3": """
    Doctor: Hello. So this is Arjun, 12 years old?
    Parent: Yes doctor. We found out he has diabetes 6 months ago. He has not been well lately.
    Doctor: What symptoms is he having?
    Parent: He is very tired, drinking a lot of water and going to the bathroom many times.
    Doctor: Arjun, are you having any stomach pain?
    Patient: Yes a little. And I feel dizzy sometimes.
    Doctor: His HbA1c is 8.9 percent. That is higher than our target of 7.5 for pediatric patients.
    Parent: Should we change his insulin?
    Doctor: Yes. His fasting glucose is 195. We will adjust his insulin dose. For children his weight of 42 kilograms the dose should be around 0.8 units per kilogram per day total.
    Parent: He also had a cold last week, could that have affected the sugar?
    Doctor: Yes illness can raise blood sugar levels. His hemoglobin is also slightly low at 11.8 so we will add iron supplements.
    """,
    "respiratory_consultation.mp3": """
    Doctor: Come in. How long have you had this cough?
    Patient: About 10 days doctor. It started as a normal cold but now I have fever and green phlegm.
    Doctor: Any chest pain when you breathe?
    Patient: Yes on the right side when I take a deep breath.
    Doctor: How high has your fever been?
    Patient: 38.9 degrees at home last night.
    Doctor: Your oxygen saturation is 94 percent on room air. Respiratory rate is 22. I can hear reduced breath sounds on the right.
    Patient: Is it serious?
    Doctor: Your blood work shows WBC of 14500 which is elevated. CRP is 45. Procalcitonin is 0.8 which suggests bacterial infection.
    Patient: Do I need to go to hospital?
    Doctor: I am going to start you on amoxicillin clavulanate 625 milligrams twice daily and order a chest X-ray. I want to see you again in 3 days. If your fever gets above 39.5 or breathing gets worse go to emergency immediately.
    Patient: I have mild asthma. Will the antibiotics affect that?
    Doctor: We will also continue your inhaler. Use salbutamol if you feel breathless.
    """,
}


def generate_specialty_consultations():
    """Generate Phase 4 specialty consultation audio files."""
    if not GTTS_AVAILABLE:
        print("Cannot generate audio - gTTS not available")
        return False

    all_success = True
    for filename, dialogue in SPECIALTY_SCRIPTS.items():
        try:
            print(f"Generating {filename}...")
            output_path = AUDIO_DIR / filename
            tts = gTTS(text=dialogue, lang="en", slow=False)
            tts.save(str(output_path))
            print(f"Generated: {output_path}")
        except Exception as e:
            print(f"Failed to generate {filename}: {e}")
            all_success = False

    return all_success


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
    print()
    success3 = generate_specialty_consultations()
    
    print("\n" + "=" * 60)
    if success1 and success2 and success3:
        print("✅ All test audio files generated successfully!")
        print("\nGenerated files:")
        print("  - tests/test_consultation.mp3 (diabetes consultation)")
        print("  - tests/test_safety_trigger.mp3 (safety trigger)")
        print("  - tests/audio/cardiology_consultation.mp3")
        print("  - tests/audio/endocrinology_consultation.mp3")
        print("  - tests/audio/pediatrics_consultation.mp3")
        print("  - tests/audio/respiratory_consultation.mp3")
    else:
        print("❌ Some audio files failed to generate")
        exit(1)
    print("=" * 60)


# Made with Bob
