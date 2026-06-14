import json
from config import get_ai_client, ModelConfig

# ── System Prompts ─────────────────────────────────────────────────────────

TRIAGE_SYSTEM_PROMPT = """You are Thanzi's Triage Prioritization Agent for Malawi.
You receive a list of patients and must prioritize CHW visit order using iCCM urgency logic.

PRIORITIZATION RULES (apply in order):
1. Any patient with danger signs = RANK FIRST regardless of other factors
2. Pregnant women with danger signs = EMERGENCY, rank above all non-emergency cases
3. Children under 2 months with any illness = HIGH priority
4. Severe acute malnutrition (SAM) = HIGH priority
5. Fever with convulsion history = HIGH priority
6. Children under 5 with fever > 3 days = MEDIUM priority
7. Adults with chronic symptom progression = MEDIUM priority
8. Mild illness, stable patient = LOW priority

For each patient provide:
- A specific clinical reason for the rank
- An estimated visit duration in minutes
- Whether the CHW should call ahead to a clinic before visiting

Respond ONLY in valid JSON with no extra text:
{
  "priority_order": [
    {
      "rank": 1,
      "patient_name": "name",
      "age": "age",
      "risk_level": "HIGH / MEDIUM / LOW",
      "reason": "specific clinical reason for this priority rank",
      "action": "what the CHW must do during this visit",
      "emergency_escalation": true/false,
      "call_clinic_first": true/false,
      "estimated_visit_minutes": number
    }
  ],
  "emergency_alert": "message to send to supervisor immediately, or null",
  "high_risk_count": number,
  "total_estimated_minutes": number,
  "schedule_note": "any note about visit scheduling (e.g. start before 8am for emergency cases)"
}"""

ESCALATION_SYSTEM_PROMPT = """You are Thanzi's Emergency Escalation Agent for Malawi.
You receive a patient case and live clinic capacity data.

Your job is to:
1. Select the BEST available clinic for this specific patient
2. Generate a complete handover referral note
3. Generate an urgent supervisor alert message
4. Provide a Chichewa phrase for the CHW to say to the patient's family
5. Explain your clinic selection reasoning step by step

CLINIC SELECTION RULES:
- NEVER recommend a clinic with 0 beds for any emergency case
- For obstetric emergencies: verify blood stock and maternity beds first
- For severe malnutrition (SAM): verify malnutrition ward exists
- For general emergencies: nearest clinic with beds available wins
- If all clinics are full: recommend the one with most beds and flag as critical

Respond ONLY in valid JSON with no extra text:
{
  "recommended_clinic": {
    "name": "clinic name",
    "reason": "why this clinic was selected",
    "distance_km": number,
    "beds_available": number,
    "warnings": "any capacity warnings, or null"
  },
  "referral_note": {
    "to": "receiving clinic name",
    "from": "Thanzi Community Health System",
    "patient_name": "full name",
    "age": "age with unit",
    "condition_summary": "brief clinical summary under 30 words",
    "reason_for_referral": "specific clinical reason",
    "urgency": "EMERGENCY / URGENT / ROUTINE",
    "danger_signs_present": true/false,
    "prepared_by": "Thanzi — Community Health Agent, Malawi"
  },
  "supervisor_alert": "urgent plain-language message to district supervisor",
  "chichewa_family_message": "what the CHW says to the family in Chichewa",
  "agent_reasoning": "step by step explanation of clinic selection"
}"""

SUPERVISOR_BRIEFING_PROMPT = """You are Thanzi's Supervisor Briefing Agent for Malawi.
Generate a structured morning district health briefing based on registry statistics.

The briefing must be actionable, not just descriptive.
Each recommended action must be specific and assignable to a person or team.

Respond ONLY in valid JSON with no extra text:
{
  "briefing_date": "formatted date string",
  "district": "district name",
  "summary": "2-3 sentence executive summary of district health status today",
  "critical_cases": number,
  "total_active_cases": number,
  "new_cases_today": number,
  "clinic_alerts": [
    {
      "clinic": "clinic name",
      "issue": "specific capacity or supply issue",
      "urgency": "HIGH / MEDIUM"
    }
  ],
  "recommended_actions": [
    {
      "action": "specific action to take",
      "assigned_to": "role responsible (e.g. Senior CHW, District Pharmacist)",
      "deadline": "today / within 24 hours / this week"
    }
  ],
  "chw_coverage_status": "summary of field coverage and any gaps",
  "supply_chain_flags": ["list of supply issues or empty array"]
}"""

DHO_INTELLIGENCE_PROMPT = """You are Thanzi's District Health Officer Intelligence Agent for Malawi.
Generate a strategic district health intelligence report for a DHO.

This report should surface patterns, trends, and systemic risks
that individual supervisors may miss.

Respond ONLY in valid JSON with no extra text:
{
  "report_date": "formatted date",
  "district": "district name",
  "executive_summary": "3-4 sentence strategic summary",
  "disease_burden": {
    "top_conditions": ["ranked list of most common conditions"],
    "high_risk_villages": ["villages with highest case concentration"],
    "age_group_most_affected": "age group description"
  },
  "system_performance": {
    "referral_completion_rate": "percentage or Unknown",
    "average_response_time": "hours or Unknown",
    "escalation_rate": "percentage of cases escalated"
  },
  "resource_gaps": ["specific resource shortfalls"],
  "strategic_recommendations": [
    {
      "recommendation": "strategic action",
      "priority": "CRITICAL / HIGH / MEDIUM",
      "responsible_party": "ministry / district office / facility"
    }
  ],
  "population_risk_score": "LOW / MEDIUM / HIGH / CRITICAL"
}"""


# ── Document Engine Functions ───────────────────────────────────────────────

def triage_patient_list(patients: list) -> dict:
    """
    Agent 3 — Triage and prioritize a list of patients for CHW visit scheduling.
    Each patient must have: name, age, symptoms.
    Returns ranked visit order with clinical justification.
    """
    if not patients:
        return {
            "error": "No patients provided",
            "priority_order": [],
            "emergency_alert": None,
            "high_risk_count": 0,
            "total_estimated_minutes": 0,
            "schedule_note": ""
        }

    client = get_ai_client()
    patient_text = "Triage and prioritize these patients for today's CHW visits:\n\n"
    for i, p in enumerate(patients, 1):
        patient_text += (
            f"{i}. {p.get('name', 'Unknown')}, Age: {p.get('age', 'Unknown')}\n"
            f"   Symptoms: {p.get('symptoms', 'Not provided')}\n\n"
        )

    try:
        response = client.chat.completions.create(
            model=ModelConfig.PRIMARY_MODEL,
            messages=[
                {"role": "system", "content": TRIAGE_SYSTEM_PROMPT},
                {"role": "user", "content": patient_text}
            ],
            response_format=ModelConfig.RESPONSE_FORMAT_JSON,
            max_tokens=ModelConfig.MAX_TOKENS_TRIAGE,
        )
        result = json.loads(response.choices[0].message.content)
        result["_agent"] = "Agent 3 — Triage Prioritization"
        result["_model"] = ModelConfig.PLATFORM_LABEL
        return result
    except json.JSONDecodeError as e:
        return {
            "error": f"JSON parsing failed: {str(e)}",
            "priority_order": [],
            "emergency_alert": "Triage parsing error — review all patients manually",
            "high_risk_count": 0,
            "total_estimated_minutes": 0,
            "schedule_note": "Manual review required",
            "_agent": "Agent 3 — Triage Prioritization",
            "_model": ModelConfig.PLATFORM_LABEL
        }
    except Exception as e:
        raise RuntimeError(f"Triage agent failed: {str(e)}")


def escalate_to_facility(patient_name: str, age: str, symptoms: str,
                          risk_level: str, assessment: str,
                          clinic_registry: list,
                          emergency: bool = True) -> dict:
    """
    Agent 4 — Select best facility and generate referral documents.
    clinic_registry is a list of facility dicts from the database.
    Returns referral note, supervisor alert, and Chichewa family message.
    """
    client = get_ai_client()

    clinic_text = "\n\nLIVE FACILITY CAPACITY DATA:\n"
    for c in clinic_registry:
        malnutrition = "Yes" if c.get("malnutrition_ward") else "No"
        clinic_text += (
            f"\nFacility: {c.get('name')}\n"
            f"  Location: {c.get('location', '')}\n"
            f"  Beds Available: {c.get('beds_available', 0)}\n"
            f"  Blood Stock: {c.get('blood_stock', 'Unknown')}\n"
            f"  Maternity Beds: {c.get('maternity_beds', 0)}\n"
            f"  Malnutrition Ward: {malnutrition}\n"
            f"  Distance: {c.get('distance_km', 0)} km\n"
            f"  Status: {c.get('status', 'ACTIVE')}\n"
        )

    patient_text = (
        f"PATIENT:\n"
        f"Name: {patient_name} | Age: {age}\n"
        f"Symptoms: {symptoms}\n"
        f"Risk Level: {risk_level}\n"
        f"Clinical Assessment: {assessment}\n"
        f"Emergency Flag: {emergency}\n"
        f"{clinic_text}"
    )

    try:
        response = client.chat.completions.create(
            model=ModelConfig.PRIMARY_MODEL,
            messages=[
                {"role": "system", "content": ESCALATION_SYSTEM_PROMPT},
                {"role": "user", "content": patient_text}
            ],
            response_format=ModelConfig.RESPONSE_FORMAT_JSON,
            max_tokens=ModelConfig.MAX_TOKENS_ESCALATION,
        )
        result = json.loads(response.choices[0].message.content)
        result["_agent"] = "Agent 4 — Emergency Escalation"
        result["_model"] = ModelConfig.PLATFORM_LABEL
        result["facilities_checked"] = len(clinic_registry)
        return result
    except json.JSONDecodeError as e:
        return {
            "error": f"JSON parsing failed: {str(e)}",
            "recommended_clinic": {"name": "Nearest Available Facility",
                                   "reason": "Parsing error — default referral",
                                   "distance_km": 0, "beds_available": 0,
                                   "warnings": "Verify capacity manually"},
            "referral_note": {"urgency": "EMERGENCY",
                              "condition_summary": assessment[:100],
                              "prepared_by": "Thanzi — Community Health Agent"},
            "supervisor_alert": f"URGENT: {patient_name} requires immediate referral. Triage parsing error.",
            "chichewa_family_message": "Pitani ku chipatala mwamsanga. Nthawi yina ili yaonekeratu.",
            "agent_reasoning": "Parsing error — safety default applied",
            "_agent": "Agent 4 — Emergency Escalation",
            "_model": ModelConfig.PLATFORM_LABEL,
            "facilities_checked": len(clinic_registry)
        }
    except Exception as e:
        raise RuntimeError(f"Escalation agent failed: {str(e)}")


def generate_supervisor_briefing(district: str, total_records: int,
                                  high_risk_count: int, new_today: int,
                                  clinic_registry: list,
                                  briefing_date: str) -> dict:
    """
    Agent 5 — Generate morning district supervisor briefing.
    Pulls from registry statistics and clinic capacity.
    """
    client = get_ai_client()

    clinic_status = "\n".join([
        f"- {c.get('name')}: {c.get('beds_available', 0)} beds, "
        f"blood={c.get('blood_stock', 'Unknown')}, "
        f"maternity={c.get('maternity_beds', 0)}"
        for c in clinic_registry
    ])

    briefing_input = (
        f"District: {district}\n"
        f"Date: {briefing_date}\n"
        f"Total patient records in system: {total_records}\n"
        f"High risk cases: {high_risk_count}\n"
        f"New cases recorded today: {new_today}\n\n"
        f"Current facility capacity:\n{clinic_status}"
    )

    try:
        response = client.chat.completions.create(
            model=ModelConfig.PRIMARY_MODEL,
            messages=[
                {"role": "system", "content": SUPERVISOR_BRIEFING_PROMPT},
                {"role": "user", "content": briefing_input}
            ],
            response_format=ModelConfig.RESPONSE_FORMAT_JSON,
            max_tokens=ModelConfig.MAX_TOKENS_SUPERVISOR,
        )
        result = json.loads(response.choices[0].message.content)
        result["_agent"] = "Agent 5 — Supervisor Briefing"
        result["_model"] = ModelConfig.PLATFORM_LABEL
        return result
    except Exception as e:
        raise RuntimeError(f"Supervisor briefing agent failed: {str(e)}")


def generate_dho_intelligence(district: str, registry_stats: dict,
                               clinic_registry: list) -> dict:
    """
    Agent 6 — Generate strategic DHO intelligence report.
    Surfaces patterns and systemic risks across the district.
    """
    client = get_ai_client()

    stats_text = (
        f"District: {district}\n"
        f"Total encounters: {registry_stats.get('total_encounters', 0)}\n"
        f"High risk encounters: {registry_stats.get('high_risk', 0)}\n"
        f"Medium risk encounters: {registry_stats.get('medium_risk', 0)}\n"
        f"Low risk encounters: {registry_stats.get('low_risk', 0)}\n"
        f"Total referrals: {registry_stats.get('total_referrals', 0)}\n"
        f"Total escalations: {registry_stats.get('total_escalations', 0)}\n"
        f"Active CHWs: {registry_stats.get('active_chws', 0)}\n"
        f"Villages covered: {registry_stats.get('villages_covered', 0)}\n"
        f"Most affected villages: {registry_stats.get('top_villages', [])}\n\n"
        f"Facility status summary:\n"
    )
    for c in clinic_registry:
        stats_text += (
            f"- {c.get('name')}: status={c.get('status')}, "
            f"beds={c.get('beds_available')}, blood={c.get('blood_stock')}\n"
        )

    try:
        response = client.chat.completions.create(
            model=ModelConfig.PRIMARY_MODEL,
            messages=[
                {"role": "system", "content": DHO_INTELLIGENCE_PROMPT},
                {"role": "user", "content": stats_text}
            ],
            response_format=ModelConfig.RESPONSE_FORMAT_JSON,
            max_tokens=1400,
        )
        result = json.loads(response.choices[0].message.content)
        result["_agent"] = "Agent 6 — DHO Intelligence"
        result["_model"] = ModelConfig.PLATFORM_LABEL
        return result
    except Exception as e:
        raise RuntimeError(f"DHO intelligence agent failed: {str(e)}")


# ── Self-test block ────────────────────────────────────────────────────────
if __name__ == "__main__":
    import os
    print("=" * 60)
    print("  Thanzi — Document Engine Self-Test")
    print("=" * 60)

    if not os.environ.get("GITHUB_TOKEN"):
        print("ERROR: GITHUB_TOKEN not set.")
        exit(1)

    sample_patients = [
        {"name": "Chisomo Banda", "age": "18 months",
         "symptoms": "Fever 4 days, not eating, very weak, one convulsion"},
        {"name": "Grace Phiri", "age": "28 years",
         "symptoms": "8 months pregnant, severe headache, blurred vision, swollen hands"},
        {"name": "James Mwale", "age": "45 years",
         "symptoms": "Cough 3 weeks, night sweats, weight loss"},
        {"name": "Thandiwe Chirwa", "age": "3 years",
         "symptoms": "Mild diarrhea 1 day, still drinking, playful"},
    ]

    sample_clinics = [
        {"name": "Bwaila District Hospital", "location": "Lilongwe",
         "beds_available": 18, "blood_stock": "Available",
         "maternity_beds": 8, "malnutrition_ward": True,
         "distance_km": 4.2, "status": "ACTIVE"},
        {"name": "Area 25 Health Centre", "location": "Lilongwe",
         "beds_available": 6, "blood_stock": "Low",
         "maternity_beds": 2, "malnutrition_ward": False,
         "distance_km": 6.8, "status": "ACTIVE"},
        {"name": "Mitundu Community Hospital", "location": "Lilongwe Rural",
         "beds_available": 12, "blood_stock": "Available",
         "maternity_beds": 4, "malnutrition_ward": True,
         "distance_km": 22.5, "status": "ACTIVE"},
    ]

    print("\n[Test 1] Triage prioritization...")
    triage = triage_patient_list(sample_patients)
    print(f"  Patients triaged: {len(triage.get('priority_order', []))}")
    print(f"  High risk count: {triage.get('high_risk_count')}")
    print(f"  Emergency alert: {triage.get('emergency_alert', 'None')[:60] if triage.get('emergency_alert') else 'None'}")

    print("\n[Test 2] Emergency escalation...")
    escalation = escalate_to_facility(
        patient_name="Grace Phiri",
        age="28 years",
        symptoms="8 months pregnant, severe headache, blurred vision",
        risk_level="HIGH",
        assessment="Suspected pre-eclampsia",
        clinic_registry=sample_clinics,
        emergency=True
    )
    clinic = escalation.get("recommended_clinic", {})
    print(f"  Recommended clinic: {clinic.get('name')}")
    print(f"  Urgency: {escalation.get('referral_note', {}).get('urgency')}")
    print(f"  Chichewa message: {escalation.get('chichewa_family_message', '')[:60]}")

    print("\n[Test 3] Supervisor briefing...")
    from datetime import datetime
    briefing = generate_supervisor_briefing(
        district="Lilongwe",
        total_records=47,
        high_risk_count=8,
        new_today=3,
        clinic_registry=sample_clinics,
        briefing_date=datetime.now().strftime("%A, %B %d %Y")
    )
    print(f"  Summary: {briefing.get('summary', '')[:80]}")
    print(f"  Clinic alerts: {len(briefing.get('clinic_alerts', []))}")
    print(f"  Actions: {len(briefing.get('recommended_actions', []))}")

    print("\nDocument engine self-tests complete.")