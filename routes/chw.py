from flask import Blueprint, render_template, request, redirect, url_for, session, flash, jsonify
from database import get_db
from routes.auth import role_required
from core_ai.translation_layer import extract_patient_from_voice, assess_patient
from core_ai.document_engine import triage_patient_list, escalate_to_facility
from datetime import datetime, date
import json

chw_bp = Blueprint('chw', __name__, url_prefix='/chw')


@chw_bp.route('/')
@role_required('CHW')
def dashboard():
    chw_id = session['user_id']
    today = date.today().isoformat()

    with get_db() as conn:
        total_patients = conn.execute(
            "SELECT COUNT(*) FROM patients WHERE registered_by_chw_id = ?", (chw_id,)
        ).fetchone()[0]

        today_encounters = conn.execute(
            "SELECT COUNT(*) FROM encounters WHERE chw_id = ? AND DATE(timestamp) = ?",
            (chw_id, today)
        ).fetchone()[0]

        high_risk_open = conn.execute(
            "SELECT COUNT(*) FROM encounters WHERE chw_id = ? AND risk_level = 'HIGH' AND record_closed = 0",
            (chw_id,)
        ).fetchone()[0]

        pending_followups = conn.execute("""
            SELECT e.id, p.name, p.village, e.risk_level, e.timestamp,
                   e.recommended_action, e.follow_up_days,
                   DATE(e.timestamp, '+' || e.follow_up_days || ' days') as followup_date
            FROM encounters e
            JOIN patients p ON e.patient_id = p.national_id
            WHERE e.chw_id = ? AND e.record_closed = 0
            AND DATE(e.timestamp, '+' || e.follow_up_days || ' days') <= DATE('now', '+1 day')
            ORDER BY followup_date ASC
            LIMIT 10
        """, (chw_id,)).fetchall()

        recent_encounters = conn.execute("""
            SELECT e.id, p.name, p.village, p.age_months, e.risk_level,
                   e.timestamp, e.recommended_action, e.referral_needed,
                   e.escalated_to_supervisor, e.record_closed,
                   f.name as facility_name
            FROM encounters e
            JOIN patients p ON e.patient_id = p.national_id
            LEFT JOIN facilities f ON e.target_facility_id = f.id
            WHERE e.chw_id = ?
            ORDER BY e.timestamp DESC
            LIMIT 15
        """, (chw_id,)).fetchall()

        last_stock = conn.execute(
            "SELECT * FROM medicine_stock WHERE chw_id = ? ORDER BY reported_at DESC LIMIT 1",
            (chw_id,)
        ).fetchone()

    return render_template('dashboard_chw.html',
        total_patients=total_patients,
        today_encounters=today_encounters,
        high_risk_open=high_risk_open,
        pending_followups=pending_followups,
        recent_encounters=recent_encounters,
        last_stock=last_stock
    )


@chw_bp.route('/register-patient', methods=['GET', 'POST'])
@role_required('CHW')
def register_patient():
    error = None
    success = None

    if request.method == 'POST':
        national_id = request.form.get('national_id', '').strip()
        name        = request.form.get('name', '').strip()
        age_months  = request.form.get('age_months', '0').strip()
        gender      = request.form.get('gender', 'Unknown').strip()
        village     = request.form.get('village', '').strip()

        if not all([national_id, name, age_months]):
            error = 'National ID, name, and age are required.'
        else:
            try:
                with get_db() as conn:
                    conn.execute("""
                        INSERT INTO patients (national_id, name, age_months, gender, village, registered_by_chw_id)
                        VALUES (?, ?, ?, ?, ?, ?)
                    """, (national_id, name, int(age_months), gender, village, session['user_id']))
                success = f"Patient '{name}' registered successfully."
            except Exception as e:
                if 'UNIQUE' in str(e):
                    error = f"National ID '{national_id}' already exists in the system."
                else:
                    error = f"Registration failed: {str(e)}"

    return render_template('chw_register_patient.html', error=error, success=success)


@chw_bp.route('/assess', methods=['GET'])
@role_required('CHW')
def assess():
    with get_db() as conn:
        patients = conn.execute("""
            SELECT p.national_id, p.name, p.village, p.age_months, p.gender,
                   e.symptoms_english, e.assessment_notes, e.recommended_action,
                   e.risk_level, e.timestamp, e.iccm_protocol_applied
            FROM patients p
            LEFT JOIN encounters e ON e.id = (
                SELECT id FROM encounters
                WHERE patient_id = p.national_id
                ORDER BY timestamp DESC LIMIT 1
            )
            WHERE p.registered_by_chw_id = ?
            ORDER BY p.name
        """, (session['user_id'],)).fetchall()
    return render_template('chw_assess.html', patients=patients)


@chw_bp.route('/api/voice-extract', methods=['POST'])
@role_required('CHW')
def voice_extract():
    data = request.json
    raw_text = data.get('text', '')
    if not raw_text:
        return jsonify({'error': 'No text provided'}), 400
    try:
        result = extract_patient_from_voice(raw_text)
        return jsonify(result)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@chw_bp.route('/api/assess', methods=['POST'])
@role_required('CHW')
def api_assess():
    data = request.json
    try:
        result = assess_patient(
            patient_name=data.get('patient_name', 'Unknown'),
            age=data.get('age', 'Unknown'),
            village=data.get('village', 'Unknown'),
            symptoms=data.get('symptoms_english', data.get('symptoms', '')),
            duration=data.get('duration', 'Unknown'),
            notes=data.get('notes', '')
        )
        return jsonify(result)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@chw_bp.route('/api/save-encounter', methods=['POST'])
@role_required('CHW')
def save_encounter():
    data = request.json
    chw_id = session['user_id']

    patient_id        = data.get('patient_id')
    symptoms_original = data.get('symptoms_original', '')
    symptoms_english  = data.get('symptoms_english', '')
    detected_language = data.get('detected_language', 'Unknown')
    risk_level        = data.get('risk_level', 'LOW')
    assessment_notes  = data.get('assessment', '')
    recommended_action = data.get('action', '')
    reasoning         = data.get('reasoning', '')
    iccm_protocol     = data.get('iccm_protocol_applied', '')
    referral_needed   = 1 if data.get('referral_needed') else 0
    escalated         = 1 if data.get('emergency_escalation') else 0
    follow_up_days    = int(data.get('follow_up_days', 3))
    chichewa_message  = data.get('chichewa_action_phrase', '')
    facility_id       = data.get('target_facility_id')
    referral_urgency  = data.get('referral_urgency', '')

    if not patient_id:
        return jsonify({'error': 'patient_id is required'}), 400

    try:
        with get_db() as conn:
            conn.execute("""
                INSERT INTO encounters
                    (patient_id, chw_id, symptoms_original, symptoms_english,
                     detected_language, risk_level, iccm_protocol_applied,
                     assessment_notes, recommended_action, reasoning,
                     referral_needed, escalated_to_supervisor,
                     chichewa_family_message, follow_up_days,
                     target_facility_id, referral_urgency)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (patient_id, chw_id, symptoms_original, symptoms_english,
                  detected_language, risk_level, iccm_protocol,
                  assessment_notes, recommended_action, reasoning,
                  referral_needed, escalated, chichewa_message,
                  follow_up_days, facility_id, referral_urgency))

            conn.execute(
                "UPDATE patients SET last_updated_at = datetime('now') WHERE national_id = ?",
                (patient_id,)
            )
        return jsonify({'success': True, 'message': 'Encounter saved.'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@chw_bp.route('/api/triage', methods=['POST'])
@role_required('CHW')
def api_triage():
    data = request.json
    patients = data.get('patients', [])
    if not patients:
        return jsonify({'error': 'No patients provided'}), 400
    try:
        result = triage_patient_list(patients)
        return jsonify(result)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@chw_bp.route('/api/escalate', methods=['POST'])
@role_required('CHW')
def api_escalate():
    data = request.json
    with get_db() as conn:
        clinics = [dict(row) for row in conn.execute(
            "SELECT * FROM facilities WHERE status != 'INACTIVE' ORDER BY distance_km"
        ).fetchall()]
    try:
        result = escalate_to_facility(
            patient_name=data.get('patient_name', 'Unknown'),
            age=data.get('age', 'Unknown'),
            symptoms=data.get('symptoms', ''),
            risk_level=data.get('risk_level', 'HIGH'),
            assessment=data.get('assessment', ''),
            clinic_registry=clinics,
            emergency=data.get('emergency', True)
        )
        return jsonify(result)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@chw_bp.route('/api/report-stock', methods=['POST'])
@role_required('CHW')
def report_stock():
    data = request.json
    chw_id = session['user_id']
    try:
        with get_db() as conn:
            conn.execute("""
                INSERT INTO medicine_stock (chw_id, ors, paracetamol, amoxicillin, malaria_rdt, zinc, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (chw_id,
                  int(data.get('ors', 0)),
                  int(data.get('paracetamol', 0)),
                  int(data.get('amoxicillin', 0)),
                  int(data.get('malaria_rdt', 0)),
                  int(data.get('zinc', 0)),
                  data.get('notes', '')))
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@chw_bp.route('/api/close-encounter/<int:encounter_id>', methods=['POST'])
@role_required('CHW')
def close_encounter(encounter_id):
    with get_db() as conn:
        conn.execute(
            "UPDATE encounters SET record_closed = 1 WHERE id = ? AND chw_id = ?",
            (encounter_id, session['user_id'])
        )
    return jsonify({'success': True})


@chw_bp.route('/api/medicine-recommend', methods=['POST'])
@role_required('CHW')
def medicine_recommend():
    from config import get_ai_client, ModelConfig

    data = request.json
    chw_id = session['user_id']

    with get_db() as conn:
        last_stock = conn.execute(
            "SELECT * FROM medicine_stock WHERE chw_id = ? ORDER BY reported_at DESC LIMIT 1",
            (chw_id,)
        ).fetchone()

    if not last_stock:
        return jsonify({'error': 'No stock reported yet. Report your medicine stock first on the Home page.'}), 400

    stock_summary = f"""
CHW Current Medicine Stock:
- ORS Sachets: {last_stock['ors']} units
- Paracetamol: {last_stock['paracetamol']} units
- Amoxicillin: {last_stock['amoxicillin']} units
- Malaria RDTs: {last_stock['malaria_rdt']} units
- Zinc Tablets: {last_stock['zinc']} units

Patient Assessment:
- Diagnosis: {data.get('assessment', '')}
- Risk Level: {data.get('risk_level', '')}
- iCCM Protocol: {data.get('iccm_protocol_applied', '')}
- Age: {data.get('age', '')}
- Symptoms: {data.get('symptoms_english', data.get('symptoms', ''))}
"""

    prompt = """You are Thanzi's Medicine Recommendation Agent for Malawi.
Based on the CHW's current stock and patient assessment, recommend specific medicines and dosages.

RULES:
- Only recommend medicines the CHW actually has in stock
- If stock is 0 or too low, flag it and suggest referral
- Follow WHO/iCCM dosage guidelines for Malawi
- Be specific about dosage, frequency, and duration
- Flag any dangerous stock shortages

Respond ONLY in valid JSON:
{
  "recommendations": [
    {
      "medicine": "medicine name",
      "dose": "specific dose",
      "frequency": "how often",
      "duration": "how many days",
      "units_needed": 0,
      "units_available": 0,
      "sufficient": true
    }
  ],
  "stock_warnings": [],
  "refer_due_to_stock": false,
  "referral_reason": null,
  "general_advice": "any additional advice for the CHW"
}"""

    try:
        client = get_ai_client()
        response = client.chat.completions.create(
            model=ModelConfig.PRIMARY_MODEL,
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": stock_summary}
            ],
            response_format={"type": "json_object"},
            max_tokens=800,
        )
        result = json.loads(response.choices[0].message.content)
        result['_agent'] = 'Agent 7 — Medicine Recommendation'
        result['_model'] = ModelConfig.PLATFORM_LABEL
        return jsonify(result)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@chw_bp.route('/patients')
@role_required('CHW')
def patients():
    with get_db() as conn:
        patient_list = conn.execute("""
            SELECT p.*, COUNT(e.id) as encounter_count,
                   MAX(e.timestamp) as last_encounter,
                   MAX(e.risk_level) as highest_risk
            FROM patients p
            LEFT JOIN encounters e ON p.national_id = e.patient_id
            WHERE p.registered_by_chw_id = ?
            GROUP BY p.national_id
            ORDER BY p.name
        """, (session['user_id'],)).fetchall()
    return render_template('chw_patients.html', patients=patient_list)