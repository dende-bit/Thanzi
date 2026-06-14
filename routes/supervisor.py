from flask import Blueprint, render_template, request, session, jsonify
from database import get_db
from routes.auth import role_required
from core_ai.document_engine import generate_supervisor_briefing
from datetime import datetime, date

supervisor_bp = Blueprint('supervisor', __name__, url_prefix='/supervisor')


@supervisor_bp.route('/')
@role_required('SUPERVISOR')
def dashboard():
    today = date.today().isoformat()

    with get_db() as conn:

        total_patients = conn.execute(
            "SELECT COUNT(*) FROM patients"
        ).fetchone()[0]

        total_encounters = conn.execute(
            "SELECT COUNT(*) FROM encounters"
        ).fetchone()[0]

        high_risk = conn.execute(
            "SELECT COUNT(*) FROM encounters WHERE risk_level = 'HIGH' AND record_closed = 0"
        ).fetchone()[0]

        new_today = conn.execute(
            "SELECT COUNT(*) FROM encounters WHERE DATE(timestamp) = ?", (today,)
        ).fetchone()[0]

        escalated_pending = conn.execute(
            "SELECT COUNT(*) FROM encounters WHERE escalated_to_supervisor = 1 AND supervisor_feedback = ''"
        ).fetchone()[0]

        active_chws = conn.execute(
            "SELECT COUNT(*) FROM users WHERE role = 'CHW' AND status = 'ACTIVE'"
        ).fetchone()[0]

        facilities = conn.execute(
            "SELECT * FROM facilities ORDER BY name"
        ).fetchall()

        escalated_cases = conn.execute("""
            SELECT e.id, p.name as patient_name, p.village, p.age_months,
                   e.risk_level, e.timestamp, e.symptoms_english,
                   e.assessment_notes, e.recommended_action,
                   e.supervisor_feedback, e.referral_urgency,
                   u.full_name as chw_name, f.name as facility_name
            FROM encounters e
            JOIN patients p ON e.patient_id = p.national_id
            JOIN users u ON e.chw_id = u.id
            LEFT JOIN facilities f ON e.target_facility_id = f.id
            WHERE e.escalated_to_supervisor = 1
            AND e.supervisor_feedback = ''
            ORDER BY e.timestamp DESC
            LIMIT 20
        """).fetchall()

        recent_high_risk = conn.execute("""
            SELECT e.id, p.name as patient_name, p.village, p.age_months,
                   e.risk_level, e.timestamp, e.symptoms_english,
                   e.recommended_action, e.referral_needed,
                   u.full_name as chw_name, f.name as facility_name
            FROM encounters e
            JOIN patients p ON e.patient_id = p.national_id
            JOIN users u ON e.chw_id = u.id
            LEFT JOIN facilities f ON e.target_facility_id = f.id
            WHERE e.risk_level = 'HIGH' AND e.record_closed = 0
            ORDER BY e.timestamp DESC
            LIMIT 15
        """).fetchall()

        chw_activity = conn.execute("""
            SELECT u.id, u.full_name, u.catchment_area,
                   COUNT(e.id) as total_encounters,
                   SUM(CASE WHEN DATE(e.timestamp) = ? THEN 1 ELSE 0 END) as today_encounters,
                   SUM(CASE WHEN e.risk_level = 'HIGH' THEN 1 ELSE 0 END) as high_risk_count
            FROM users u
            LEFT JOIN encounters e ON u.id = e.chw_id
            WHERE u.role = 'CHW' AND u.status = 'ACTIVE'
            GROUP BY u.id
            ORDER BY today_encounters DESC
        """, (today,)).fetchall()

    stats = {
        'total_patients': total_patients,
        'total_encounters': total_encounters,
        'high_risk': high_risk,
        'new_today': new_today,
        'escalated_pending': escalated_pending,
        'active_chws': active_chws,
    }

    return render_template('dashboard_supervisor.html',
        stats=stats,
        facilities=facilities,
        escalated_cases=escalated_cases,
        recent_high_risk=recent_high_risk,
        chw_activity=chw_activity
    )


@supervisor_bp.route('/api/feedback/<int:encounter_id>', methods=['POST'])
@role_required('SUPERVISOR')
def submit_feedback(encounter_id):
    data = request.json
    feedback = data.get('feedback', '').strip()
    if not feedback:
        return jsonify({'error': 'Feedback cannot be empty'}), 400
    try:
        with get_db() as conn:
            conn.execute("""
                UPDATE encounters
                SET supervisor_feedback = ?,
                    supervisor_id = ?
                WHERE id = ?
            """, (feedback, session['user_id'], encounter_id))
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@supervisor_bp.route('/api/briefing', methods=['GET'])
@role_required('SUPERVISOR')
def get_briefing():
    today = date.today().isoformat()

    with get_db() as conn:
        total_records = conn.execute(
            "SELECT COUNT(*) FROM encounters"
        ).fetchone()[0]

        high_risk_count = conn.execute(
            "SELECT COUNT(*) FROM encounters WHERE risk_level = 'HIGH' AND record_closed = 0"
        ).fetchone()[0]

        new_today = conn.execute(
            "SELECT COUNT(*) FROM encounters WHERE DATE(timestamp) = ?", (today,)
        ).fetchone()[0]

        facilities = [dict(row) for row in conn.execute(
            "SELECT * FROM facilities ORDER BY name"
        ).fetchall()]

    try:
        briefing = generate_supervisor_briefing(
            district="Lilongwe",
            total_records=total_records,
            high_risk_count=high_risk_count,
            new_today=new_today,
            clinic_registry=facilities,
            briefing_date=datetime.now().strftime("%A, %B %d %Y")
        )
        return jsonify(briefing)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@supervisor_bp.route('/api/close-encounter/<int:encounter_id>', methods=['POST'])
@role_required('SUPERVISOR')
def close_encounter(encounter_id):
    with get_db() as conn:
        conn.execute(
            "UPDATE encounters SET record_closed = 1 WHERE id = ?",
            (encounter_id,)
        )
    return jsonify({'success': True})