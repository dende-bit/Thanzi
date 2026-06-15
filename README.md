# Thanzi 🇲🇼

**Thanzi** means *health* in Chichewa. That is the whole point.

Built in Mzuzu, Malawi. One week. One developer.
Submitted to the **Microsoft Agents League Hackathon 2026**.

---

> I built this because I know what happens when a Community Health Worker
> stands in front of a sick child at 6am in a village with no clinic nearby,
> no signal, and no training manual — and guesses wrong.
>
> Children die from that guess.
>
> — Daniel Kayira, Mzuzu
> -https://youtu.be/CRAqdP_pnao

---

## What this is

Thanzi is a clinical intelligence system for Community Health Workers
and Health Surveillance Assistants in Malawi. It runs in any browser
on any device. A CHW can use it on a borrowed phone, a health centre
desktop, or their own basic smartphone — without installing anything,
without a Google account, without storage space, without waiting for
IT support.

Malawi already has digital health tools. CommCare. DHIS2. OpenLMIS.
Each one does something well. None of them talk to each other.

An HSA uses one app to assess a child. That app has no idea whether
the clinic down the road has amoxicillin. It does not know if Bwaila
District Hospital has maternity beds available. It does not tell the
supervisor anything until someone pulls a report at the end of the
week. The data goes up. Nothing comes back down.

Thanzi is not another data collection tool. It is the connective
tissue those systems were never designed to be — the layer that
connects the HSA in the field, the drug supply in their bag, the
beds in the facility, and the supervisor at the district office, in
one place, in real time, without a single app installation.

---

## How it works

Six AI agents. Four user roles. One web app.

Every agent runs on **Microsoft Phi-4 via Azure AI Foundry**
Browser (any device, any phone)

│

▼

Flask Backend

│

├── Agent 1: Voice Extraction      (translation_layer.py)

├── Agent 2: Clinical Assessment   (translation_layer.py)

├── Agent 3: Triage Prioritization (document_engine.py)

├── Agent 4: Clinic Bridge         (document_engine.py)

├── Agent 5: Supervisor Briefing   (document_engine.py)

└── Agent 6: DHO Intelligence      (document_engine.py)

│

▼

Microsoft Phi-4 — Azure AI Foundry

│

▼

SQLite Database

(facilities, users, patients,

encounters, medicine_stock)

All agents return strict JSON. Flask parses it. Nothing reaches
the CHW's screen that was not verified by the model.

---

## The six agents

**Agent 1 — Voice Extraction**
A CHW speaks or types in Chichewa, English, or a mix. Agent 1
extracts name, age, village, symptoms, duration, and danger signs.
It understands that *maliro* means fever, *msongo* means diarrhea,
*mimba* means pregnancy. It handles the way people in Malawi
actually speak about illness — not the way a textbook describes it.

**Agent 2 — Clinical Assessment**
Runs the full iCCM protocol in the correct sequence: danger signs
first, then illness classification across four tracks — fever and
malaria, cough and pneumonia, diarrhea and dehydration, malnutrition
— then special populations including pregnant women, newborns under
two months, and TB suspects. Returns LOW, MEDIUM, or HIGH risk with
full clinical reasoning and a Chichewa phrase the CHW says to
the family.

**Agent 3 — Triage Prioritization**
The CHW selects patients from their registered list. Each patient
loads with their last recorded symptoms already filled in — no
retyping, no searching through paper records. Agent 3 ranks the
visits by clinical urgency and estimates how long each visit should
take. The CHW leaves home knowing who is most at risk before they
take a single step.

**Agent 4 — Clinic Bridge**
Before any referral is written, Agent 4 reads the live facility
table: beds available, blood stock, maternity beds, malnutrition
ward, distance from the patient. It will never route a patient to
a facility with zero beds. This is the thing existing tools cannot
do — bridge the gap between the community and the facility in real
time. It generates a complete referral note the CHW hands to the
patient to carry.

**Agent 5 — Supervisor Briefing**
One button. The supervisor gets a structured morning summary: open
HIGH risk cases, clinic capacity warnings, recommended actions with
deadlines, and who is responsible for each one. Not a weekly report.
Not an aggregate. Today. Now.

**Agent 6 — DHO Intelligence**
Strategic view for the District Health Officer: disease burden by
village, CHW performance trends, resource gaps, outbreak signals,
and ranked policy recommendations. It surfaces patterns that no
individual supervisor can see from where they sit.

---

## The five problems it solves

These are documented, systemic realities in Malawi's public
health system — not invented scenarios.

**1. The wrong diagnosis**

HSAs complete a basic training course and then work alone serving
communities of over 1,000 people. When a child presents with fever,
fast breathing, and weakness — is that malaria, pneumonia, or severe
malnutrition? The difference determines whether the child lives.

A peer-reviewed evaluation of Malawi's iCCM program found that HSAs
correctly classified sick children only 58% of the time using paper
tools. With digital decision support, accuracy rose to 81%. Thanzi
gives every HSA that decision support, in their pocket, in their
language, on any device they can find.

**2. The useless referral**

A CHW refers a mother in labour to the nearest hospital. She
travels kilometres. The maternity ward has no beds. She is turned
away. Her condition deteriorates.

Maternal mortality audits in Malawi consistently cite blind
referrals — patients arriving at full facilities with no one warned
in advance — as a key driver of preventable deaths. Agent 4
eliminates this by checking capacity before the referral is written.
Existing diagnostic apps cannot do this. They do not know what is
happening inside the hospital. Thanzi does.

**3. The empty medicine bag**

HSAs carry ORS, paracetamol, amoxicillin, malaria RDTs, and zinc.
When they run out, patients go untreated. Under the current system,
no one knows until the CHW submits a paper form at the end of
the month.

Systematic reviews of community health programs across sub-Saharan
Africa show CHWs are stocked out of essential medicines nearly one
third of the time. Thanzi lets CHWs report stock levels by speaking
into their phone. The supervisor sees it the same day — not four
weeks later.

**4. The invisible emergency**

When a CHW encounters a child with convulsions or a pregnant woman
with severe headache and blurred vision, they call their supervisor
— if they have airtime. If not, they handle it alone and hope
it resolves.

Thanzi escalates automatically. The supervisor dashboard shows
the case immediately, with full clinical context already attached.
It does not disappear into a call log. It does not wait for someone
to pull a report. It is there, visible, demanding a response.

**5. The outbreak nobody noticed**

During the 2022–2023 cholera outbreak — the deadliest in Malawi's
recorded history — early cases were treated as isolated incidents.
Weekly aggregate reporting meant the cluster was invisible until
it had already spread across multiple districts.

Thanzi flags a potential cluster the moment two patients from the
same village present with similar symptoms within seven days. This
is not done by asking an AI to guess — it runs a direct SQL query
over the encounter history, then passes the confirmed signal to
Phi-4 to turn it into an actionable brief for the DHO. The data
layer finds it. The AI explains it.

---

## Three real use cases

**A CHW starting their day**

It is 6am. The CHW opens Thanzi in their phone browser. Three
follow-up visits are scheduled. They click Multi-Triage, select
their patients — last recorded symptoms load automatically — and
in under a minute receive a ranked visit order with the clinical
reason for each ranking. They know what they are walking into
before they leave their house.

**A supervisor at 7am**

The dashboard shows an escalation. A CHW has flagged a patient:
8 months pregnant, severe headache, blurred vision. Agent 4 has
already checked the facilities in Lilongwe district. Bwaila
District Hospital has maternity beds available and blood in stock.
The referral note is generated. The supervisor calls ahead.
The patient arrives and is admitted without delay.

**A District Health Officer on Monday morning**

The Command Hub shows a flag: four children in the same village
presenting with diarrhea and vomiting in the last seven days.
The database caught the cluster. The DHO sees it on Monday
morning. Under the previous system, she would have seen it in
a monthly report three weeks from now. She dispatches a response
team the same day.

---

## What is actually built

This is not a prototype with mocked responses.

The database schema is fully relational with foreign keys,
cascading deletes, and indexed lookups. All six agents are live
API calls to Microsoft Phi-4 — not pre-written strings.
Agent 4's referral routing reads the actual facility table in
real time. The outbreak detection is a real SQL query over the
encounter history — not an AI guess. Role-based access control
is enforced on every route including every API endpoint.

**What is not built yet:** offline mode, SMS integration,
WhatsApp channel, PDF referral generation, national ID lookup.
These are Phase 2. They are not listed as features because they
do not exist yet.

---

## Running it locally

```bash
git clone https://github.com/dende-bit/Thanzi.git
cd Thanzi

pip install flask openai

# Windows
set GITHUB_TOKEN=your_github_personal_access_token

# Mac or Linux
export GITHUB_TOKEN=your_github_personal_access_token

python app.py
```

Open `http://127.0.0.1:5000`

Log in with `admin` / `thanzi_admin_2026`

From the Admin panel, register a CHW, a Supervisor, and a DHO
account. Log in as each one to see what they see.

---

## File structure
Thanzi/

├── app.py                      Flask app factory

├── config.py                   Azure AI Foundry client

├── database.py                 Schema, indexes, seed data

├── core_ai/

│   ├── translation_layer.py    Agents 1 and 2

│   └── document_engine.py      Agents 3, 4, 5, and 6

├── routes/

│   ├── auth.py                 Login and role decorators

│   ├── admin.py                Admin routes

│   ├── chw.py                  CHW routes and AI endpoints

│   ├── supervisor.py           Supervisor routes

│   └── dho.py                  DHO routes

└── templates/                  One HTML file per view

---

## Phase 2 roadmap

- Offline-first PWA — service worker caching so the system
  works when the network drops and syncs when it returns
- WhatsApp Business API — CHWs submit patient data via
  WhatsApp, no browser required
- Excel import — facility managers upload existing stock
  sheets, AI extracts all values automatically
- PDF referral notes — printable card generated per patient
- SMS fallback — for CHWs with basic feature phones
- National ID integration — Malawi NRB API lookup

---

## About

Built by **Daniel Kayira** — Mzuzu, Malawi — June 2026.

I am from Mzuzu. I built this system with Lilongwe district
as the pilot — using real facilities: Bwaila District Hospital,
Area 25 Health Centre, and Mitundu Community Hospital — because
Lilongwe represents the densest concentration of CHWs and the
most complex referral network in Malawi.

The problems Thanzi solves are not unique to Lilongwe.
They exist in Mzuzu, in Blantyre, in Dedza, in every district
where an HSA is working alone with a paper form and no support
system behind them.

I know what it looks like when a child who could have been
saved was not saved because no one had the right information
at the right moment. That knowledge is why this exists.

---

*Submitted to the Microsoft Agents League Hackathon 2026*

*#AgentsLeague2026 #MalawiAI #Thanzi #HackForGood #MicrosoftAgents*
(`https://models.inference.ai.azure.com`). The only credential
needed is a free GitHub Personal Access Token — meaning any
district health office can run this with zero cloud budget.
