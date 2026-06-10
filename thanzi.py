from groq import Groq

import os
client = Groq(api_key=os.environ.get("GROQ_API_KEY"))

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
    conversation_history.append({
        "role": "user", 
        "content": user_message
    })
    
    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "system", "content": system_prompt}] + conversation_history
    )
    
    assistant_message = response.choices[0].message.content
    conversation_history.append({
        "role": "assistant",
        "content": assistant_message
    })
    
    return assistant_message

print("=" * 50)
print("   THANZI - Community Health Agent")
print("   Serving Malawi's Community Health Workers")
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