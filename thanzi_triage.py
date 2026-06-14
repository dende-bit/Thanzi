from openai import OpenAI
import json
from datetime import datetime
import os

# Microsoft Phi-4 via Azure AI Foundry (GitHub Models free tier)
github_token = os.environ.get("GITHUB_TOKEN")
client = OpenAI(
    base_url="https://models.inference.ai.azure.com",
    api_key=github_token,
)

system_prompt = """You are Thanzi, an AI health agent for Community Health Workers (CHWs) in Malawi.

When given a list of patients, you must:
1. Assess each patient's risk level
2. Prioritize who the CHW should visit FIRST based on urgency
3. Recommend specific actions for each patient
4. Flag any cases needing immediate emergency escalation to supervisor

Always respond in valid JSON format exactly like this:
{
  "priority_order": [
    {
      "rank": 1,
      "patient_name": "name",
      "age": "age",
      "risk_level": "HIGH/MEDIUM/LOW",
      "reason": "why this rank",
      "action": "what CHW should do",
      "emergency_escalation": true/false
    }
  ],
  "emergency_alert": "message to supervisor if any emergencies, or null",
  "high_risk_count": number
}"""

# Sample patients for Malawi context
patients = [
    {
        "name": "Chisomo Banda",
        "age": "18 months",
        "symptoms": "fever for 4 days, not eating, very weak",
        "last_visit": "2 weeks ago"
    },
    {
        "name": "Grace Phiri",
        "age": "28 years",
        "symptoms": "8 months pregnant, severe headache, blurred vision, swollen hands",
        "last_visit": "1 month ago"
    },
    {
        "name": "James Mwale",
        "age": "45 years",
        "symptoms": "cough for 2 weeks, night sweats, weight loss",
        "last_visit": "3 weeks ago"
    },
    {
        "name": "Thandiwe Chirwa",
        "age": "3 years",
        "symptoms": "mild diarrhea for 1 day, still drinking, playful",
        "last_visit": "1 week ago"
    },
    {
        "name": "Mary Tembo",
        "age": "6 months",
        "symptoms": "cough and fast breathing for 2 days, not feeding well",
        "last_visit": "never"
    }
]


def triage_patients(patient_list):
    if not github_token:
        raise EnvironmentError(
            "GITHUB_TOKEN not set. Get one at github.com/settings/tokens and run:\n"
            "  export GITHUB_TOKEN=your_token"
        )

    patient_text = "Please triage these patients and prioritize my visits today:\n\n"
    for i, p in enumerate(patient_list, 1):
        patient_text += f"{i}. {p['name']}, {p['age']}: {p['symptoms']} (Last visit: {p['last_visit']})\n"

    response = client.chat.completions.create(
        model="Phi-4",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": patient_text}
        ],
        response_format={"type": "json_object"},
        max_tokens=1000,
    )

    return json.loads(response.choices[0].message.content)


def display_triage_results(results):
    print("\n" + "=" * 60)
    print("   THANZI TRIAGE REPORT")
    print(f"   Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("   Model: Microsoft Phi-4 via Azure AI Foundry")
    print("=" * 60)

    if results.get("emergency_alert"):
        print(f"\n🚨 EMERGENCY ALERT TO SUPERVISOR:")
        print(f"   {results['emergency_alert']}")
        print()

    print(f"High risk: {results['high_risk_count']}")
    print("\nVISIT PRIORITY ORDER:")
    print("-" * 60)

    for patient in results["priority_order"]:
        risk = patient["risk_level"]
        flag = "🔴" if risk == "HIGH" else "🟡" if risk == "MEDIUM" else "🟢"

        print(f"\n#{patient['rank']} {flag} {patient['patient_name']} ({patient['age']})")
        print(f"   Risk: {risk}")
        print(f"   Why: {patient['reason']}")
        print(f"   Action: {patient['action']}")
        if patient.get("emergency_escalation"):
            print(f"   ⚠️  ESCALATE TO SUPERVISOR IMMEDIATELY")

    print("\n" + "=" * 60)


print("=" * 60)
print("   THANZI — Community Health Agent")
print("   Triage System | Malawi")
print("   Powered by Microsoft Phi-4 (Azure AI Foundry)")
print("=" * 60)
print("Running triage on patients...\n")

try:
    results = triage_patients(patients)
    display_triage_results(results)
except EnvironmentError as e:
    print(f"\n❌ Setup Error: {e}")
except Exception as e:
    print(f"\n❌ Error: {e}")