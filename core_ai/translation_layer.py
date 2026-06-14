import json
from config import get_ai_client, ModelConfig

# ── System Prompts ─────────────────────────────────────────────────────────

EXTRACTION_SYSTEM_PROMPT = """You are Thanzi's Voice Extraction Agent for Community Health Workers in Malawi.

A CHW has spoken or typed a patient description in Chichewa, English, or a mix of both.

Your responsibilities:
1. Detect the language used (Chichewa, English, or Mixed)
2. Extract all identifiable patient details from the raw input
3. Translate symptoms to English for clinical processing
4. Preserve the original language text exactly as spoken for the patient record
5. Extract village names, which in Malawi often sound like: Mtendere, Chisomo, Mpatsa, Bvuto, Chikondi

Common Chichewa health terms you must recognise:
- matenda = illness / sickness
- maliro = fever
- msongo = diarrhea
- kufupa = vomiting
- mwana = child
- mayi = mother / woman
- bambo = father / man
- mimba = pregnancy
- kulibe = without / lacking
- oopsa = serious / dangerous
- bwino = fine / well
- chanjira = vaccination
- kufa = dying

Respond ONLY in valid JSON with no extra text:
{
  "patient_name": "extracted full name or Unknown",
  "age": "extracted age with unit (e.g. 8 months, 3 years) or Unknown",
  "gender": "Male / Female / Unknown",
  "village": "extracted village name or Unknown",
  "symptoms_original": "symptoms exactly as spoken in original language",
  "symptoms_english": "full English translation of symptoms",
  "duration": "duration of illness (e.g. 3 days) or Unknown",
  "pregnancy_noted": true/false,
  "danger_signs_mentioned": true/false,
  "additional_notes": "any other relevant details",
  "detected_language": "Chichewa / English / Mixed",
  "confidence": "HIGH / MEDIUM / LOW"
}"""

ASSESSMENT_SYSTEM_PROMPT = """You are Thanzi's Clinical Assessment Agent for Malawi.
You follow the iCCM (Integrated Community Case Management) protocol used by
Community Health Workers across sub-Saharan Africa.

iCCM ASSESSMENT SEQUENCE — follow this order strictly:

STEP 1 — CHECK DANGER SIGNS (any one = HIGH risk, likely emergency):
  - Unable to drink or breastfeed
  - Vomits everything
  - Convulsions now or in last 24 hours
  - Unconscious or cannot be woken
  - Severe chest indrawing
  - Stridor when calm
  - Very severe febrile disease signs

STEP 2 — CLASSIFY MAIN ILLNESS:
  Fever track: temperature > 37.5°C or history of fever
    → Malaria RDT logic, duration, stiff neck (meningitis flag)
  Cough track: breathing rate, chest indrawing, stridor
    → Fast breathing (>50 breaths/min under 1yr, >40 over 1yr) = pneumonia
  Diarrhea track: duration, blood in stool, dehydration signs
    → Skin pinch, sunken eyes, drinking status
  Malnutrition track: MUAC < 115mm = SAM, 115-125 = MAM
    → Bilateral pitting oedema

STEP 3 — SPECIAL POPULATIONS:
  Pregnant women: danger signs = severe headache, blurred vision,
    swollen face/hands, bleeding, convulsions, severe abdominal pain
  Newborns (< 2 months): any danger sign = EMERGENCY
  TB suspects: cough > 2 weeks, night sweats, weight loss, haemoptysis

STEP 4 — DETERMINE RISK LEVEL:
  HIGH: any danger sign, SAM, obstetric emergency, suspected meningitis,
        severe dehydration, newborn danger sign
  MEDIUM: fast breathing, diarrhea with some dehydration, MAM,
          fever > 3 days, suspected TB
  LOW: mild illness, no danger signs, adequate feeding and drinking

Respond ONLY in valid JSON with no extra text:
{
  "risk_level": "HIGH / MEDIUM / LOW",
  "assessment": "detailed clinical findings in plain language",
  "action": "specific immediate action for the CHW to take",
  "referral_needed": true/false,
  "emergency_escalation": true/false,
  "reasoning": "step by step iCCM reasoning showing which step triggered the decision",
  "iccm_protocol_applied": "specific iCCM classification used",
  "danger_signs_identified": ["list of danger signs found or empty array"],
  "follow_up_days": 1-7,
  "chichewa_action_phrase": "one sentence in Chichewa telling the CHW what to tell the family"
}"""

TRANSLATION_SYSTEM_PROMPT = """You are a precise medical translator for Malawi.
Translate the given text between English and Chichewa accurately.
Preserve all medical terms. Do not add or remove clinical meaning.

Respond ONLY in valid JSON:
{
  "original_text": "the original input text",
  "translated_text": "the full translation",
  "source_language": "English / Chichewa",
  "target_language": "English / Chichewa",
  "medical_terms_preserved": ["list of key medical terms in the translation"]
}"""


# ── Agent Functions ─────────────────────────────────────────────────────────

def extract_patient_from_voice(raw_input: str) -> dict:
    """
    Agent 1 — Extract structured patient data from raw voice or text input.
    Handles Chichewa, English, and mixed language input.
    Returns a structured dict with patient demographics and symptoms.
    """
    client = get_ai_client()
    try:
        response = client.chat.completions.create(
            model=ModelConfig.PRIMARY_MODEL,
            messages=[
                {"role": "system", "content": EXTRACTION_SYSTEM_PROMPT},
                {"role": "user", "content": f"Extract patient details from this input:\n\n{raw_input}"}
            ],
            response_format=ModelConfig.RESPONSE_FORMAT_JSON,
            max_tokens=ModelConfig.MAX_TOKENS_EXTRACTION,
        )
        result = json.loads(response.choices[0].message.content)
        result["_agent"] = "Agent 1 — Voice Extraction"
        result["_model"] = ModelConfig.PLATFORM_LABEL
        return result
    except json.JSONDecodeError as e:
        return {
            "error": f"JSON parsing failed: {str(e)}",
            "patient_name": "Unknown", "age": "Unknown",
            "gender": "Unknown", "village": "Unknown",
            "symptoms_original": raw_input,
            "symptoms_english": raw_input,
            "duration": "Unknown",
            "detected_language": "Unknown",
            "confidence": "LOW",
            "_agent": "Agent 1 — Voice Extraction",
            "_model": ModelConfig.PLATFORM_LABEL
        }
    except Exception as e:
        raise RuntimeError(f"Extraction agent failed: {str(e)}")


def assess_patient(patient_name: str, age: str, village: str,
                   symptoms: str, duration: str, notes: str = "") -> dict:
    """
    Agent 2 — Run iCCM clinical assessment on a single patient.
    Returns risk level, action, reasoning, and referral decision.
    """
    client = get_ai_client()
    patient_text = f"""Patient Name: {patient_name}
Age: {age}
Village: {village}
Symptoms (English): {symptoms}
Duration: {duration}
Additional Notes: {notes if notes else 'None'}"""

    try:
        response = client.chat.completions.create(
            model=ModelConfig.PRIMARY_MODEL,
            messages=[
                {"role": "system", "content": ASSESSMENT_SYSTEM_PROMPT},
                {"role": "user", "content": patient_text}
            ],
            response_format=ModelConfig.RESPONSE_FORMAT_JSON,
            max_tokens=ModelConfig.MAX_TOKENS_ASSESSMENT,
        )
        result = json.loads(response.choices[0].message.content)
        result["_agent"] = "Agent 2 — Clinical Assessment (iCCM)"
        result["_model"] = ModelConfig.PLATFORM_LABEL
        return result
    except json.JSONDecodeError as e:
        return {
            "error": f"JSON parsing failed: {str(e)}",
            "risk_level": "HIGH",
            "assessment": "Assessment parsing error — treat as HIGH risk",
            "action": "Refer to nearest facility immediately",
            "referral_needed": True,
            "emergency_escalation": True,
            "reasoning": "Parsing error — defaulting to HIGH for patient safety",
            "iccm_protocol_applied": "Safety default",
            "danger_signs_identified": [],
            "follow_up_days": 1,
            "chichewa_action_phrase": "Pitani ku chipatala mwamsanga.",
            "_agent": "Agent 2 — Clinical Assessment (iCCM)",
            "_model": ModelConfig.PLATFORM_LABEL
        }
    except Exception as e:
        raise RuntimeError(f"Assessment agent failed: {str(e)}")


def translate_text(text: str, target_language: str = "English") -> dict:
    """
    Standalone translation function.
    Translates between English and Chichewa preserving medical terminology.
    """
    client = get_ai_client()
    try:
        response = client.chat.completions.create(
            model=ModelConfig.PRIMARY_MODEL,
            messages=[
                {"role": "system", "content": TRANSLATION_SYSTEM_PROMPT},
                {"role": "user", "content": f"Translate this to {target_language}:\n\n{text}"}
            ],
            response_format=ModelConfig.RESPONSE_FORMAT_JSON,
            max_tokens=ModelConfig.MAX_TOKENS_TRANSLATION,
        )
        result = json.loads(response.choices[0].message.content)
        result["_agent"] = "Translation Layer"
        result["_model"] = ModelConfig.PLATFORM_LABEL
        return result
    except Exception as e:
        return {
            "error": str(e),
            "original_text": text,
            "translated_text": text,
            "source_language": "Unknown",
            "target_language": target_language,
            "medical_terms_preserved": [],
            "_agent": "Translation Layer",
            "_model": ModelConfig.PLATFORM_LABEL
        }


# ── Self-test block ────────────────────────────────────────────────────────
if __name__ == "__main__":
    import os
    print("=" * 60)
    print("  Thanzi — Translation Layer Self-Test")
    print("=" * 60)

    if not os.environ.get("GITHUB_TOKEN"):
        print("ERROR: GITHUB_TOKEN not set. Cannot run self-test.")
        print("Run: set GITHUB_TOKEN=your_token_here")
        exit(1)

    print("\n[Test 1] Chichewa voice extraction...")
    result = extract_patient_from_voice(
        "Mwana wa Grace Banda ali ndi matenda. Mwezi 8, kilogram 6.2, kulibe chanjira. "
        "Wakhala ndi fever masiku atatu ndipo sakudya."
    )
    print(f"  Patient: {result.get('patient_name')}")
    print(f"  Age: {result.get('age')}")
    print(f"  Language: {result.get('detected_language')}")
    print(f"  Symptoms (EN): {result.get('symptoms_english')}")
    print(f"  Confidence: {result.get('confidence')}")

    print("\n[Test 2] Clinical assessment...")
    assessment = assess_patient(
        patient_name="Grace Banda",
        age="8 months",
        village="Mtendere",
        symptoms="Fever for 3 days, not eating, very weak, had one convulsion this morning",
        duration="3 days"
    )
    print(f"  Risk Level: {assessment.get('risk_level')}")
    print(f"  Emergency: {assessment.get('emergency_escalation')}")
    print(f"  Protocol: {assessment.get('iccm_protocol_applied')}")
    print(f"  Action: {assessment.get('action')}")

    print("\n[Test 3] Translation...")
    translation = translate_text("The child has severe malnutrition and needs immediate referral.", "Chichewa")
    print(f"  Translated: {translation.get('translated_text')}")

    print("\nAll translation layer tests complete.")