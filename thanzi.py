from openai import OpenAI
import os

# Microsoft Phi-4 via Azure AI Foundry (GitHub Models free tier)
github_token = os.environ.get("GITHUB_TOKEN")
client = OpenAI(
    base_url="https://models.inference.ai.azure.com",
    api_key=github_token,
)

system_prompt = """You are Thanzi, an AI health agent for Community Health Workers (CHWs) 
in Malawi. You help CHWs assess patient risk, prioritize home visits, coordinate referrals 
to clinics, and escalate emergencies to supervisors.

You understand both English and Chichewa. You follow iCCM protocols used in Malawi.

When assessing a patient always check:
1. Danger signs (unable to drink, convulsions, unconscious, severe vomiting)
2. Main symptoms (fever, cough, diarrhea, malnutrition, difficulty breathing)
3. Duration of illness
4. Age and weight of patient
5. Pregnancy status if female adult

Always structure your response as:
RISK LEVEL: HIGH / MEDIUM / LOW
ASSESSMENT: (what you found)
ACTION: (what the CHW should do)
REFERRAL NEEDED: YES / NO
CHICHEWA SUMMARY: (translate key advice to Chichewa)"""

conversation_history = []

def chat_with_thanzi(user_message):
    if not github_token:
        return "❌ GITHUB_TOKEN not set. Run: export GITHUB_TOKEN=your_token"

    conversation_history.append({
        "role": "user",
        "content": user_message
    })

    try:
        response = client.chat.completions.create(
            model="Phi-4",
            messages=[{"role": "system", "content": system_prompt}] + conversation_history,
            max_tokens=1000,
        )

        assistant_message = response.choices[0].message.content
        conversation_history.append({
            "role": "assistant",
            "content": assistant_message
        })
        return assistant_message

    except Exception as e:
        return f"❌ Error: {e}"


print("=" * 50)
print("   THANZI - Community Health Agent")
print("   Serving Malawi's Community Health Workers")
print("   Powered by Microsoft Phi-4 (Azure AI Foundry)")
print("=" * 50)
print("Type your patient case below. Type 'exit' to quit.")
print()

while True:
    user_input = input("CHW: ")
    if user_input.lower() == "exit":
        print("Thanzi: Zikomo. Stay safe in the field.")
        break
    print()
    print("Thanzi:", chat_with_thanzi(user_input))
    print()