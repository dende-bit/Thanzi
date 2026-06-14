from flask import Blueprint, render_template, request, session, jsonify
from database import get_db
from routes.auth import role_required
from core_ai.document_engine import generate_dho_intelligence
from datetime import datetime, date

dho_bp = Blueprint('dho', __name__, url_prefix='/dho')


@dho_bp.route('/')
@role_required('DHO')
def dashboard():
    today = date.today().isoformat()

    with get_db() as conn:

        total_encounters = conn.execute(
            "SELECT COUNT(*) FROM encounters"
        ).fetchone()[0]

        high_risk = conn.execute(
            "SELECT COUNT(*) FROM encounters WHERE risk_level = 'HIGH'"
        ).fetchone()[0]

        medium_risk = conn.execute(
            "SELECT COUNT(*) FROM encounters WHERE risk_level = 'MEDIUM'"
        ).fetchone()[0]

        low_risk = conn.execute(
            "SELECT COUNT(*) FROM encounters WHERE risk_level = 'LOW'"
        ).fetchone()[0]

        total_referrals = conn.execute(
            "SELECT COUNT(*) FROM encounters WHERE referral_needed = 1"
        ).fetchone()[0]

        total_escalations = conn.execute(
            "SELECT COUNT(*) FROM encounters WHERE escalated_to_supervisor = 1"
        ).fetchone()[0]

        total_patients = conn.execute(
            "SELECT COUNT(*) FROM patients"
        ).fetchone()[0]

        active_chws = conn.execute(
            "SELECT COUNT(*) FROM users WHERE role = 'CHW' AND status = 'ACTIVE'"
        ).fetchone()[0]

        villages_covered = conn.execute(
            "SELECT COUNT(DISTINCT village) FROM patients WHERE village != ''"
        ).fetchone()[0]

        new_today = conn.execute(
            "SELECT COUNT(*) FROM encounters WHERE DATE(timestamp) = ?", (today,)
        ).fetchone()[0]

        facilities = conn.execute(
            "SELECT * FROM facilities ORDER BY name"
        ).fetchall()

        top_villages = conn.execute("""
            SELECT village, COUNT(*) as case_count
            FROM patients
            WHERE village != ''
            GROUP BY village
            ORDER BY case_count DESC
            LIMIT 5
        """).fetchall()

        disease_trends = conn.execute("""
            SELECT DATE(timestamp) as encounter_date,
                   COUNT(*) as total,
                   SUM(CASE WHEN risk_level = 'HIGH' THEN 1 ELSE 0 END) as high,
                   SUM(CASE WHEN risk_level = 'MEDIUM' THEN 1 ELSE 0 END) as medium,
                   SUM(CASE WHEN risk_level = 'LOW' THEN 1 ELSE 0 END) as low
            FROM encounters
            GROUP BY DATE(timestamp)
            ORDER BY encounter_date DESC
            LIMIT 14
        """).fetchall()

        chw_performance = conn.execute("""
            SELECT u.full_name, u.catchment_area,
                   COUNT(e.id) as total_encounters,
                   SUM(CASE WHEN e.risk_level = 'HIGH' THEN 1 ELSE 0 END) as high_risk,
                   SUM(CASE WHEN e.referral_needed = 1 THEN 1 ELSE 0 END) as referrals,
                   MAX(e.timestamp) as last_active
            FROM users u
            LEFT JOIN encounters e ON u.id = e.chw_id
            WHERE u.role = 'CHW' AND u.status = 'ACTIVE'
            GROUP BY u.id
            ORDER BY total_encounters DESC
        """).fetchall()

        outbreak_watch = conn.execute("""
            SELECT p.village,
                   e.symptoms_english,
                   COUNT(*) as case_count,
                   MAX(e.timestamp) as latest
            FROM encounters e
            JOIN patients p ON e.patient_id = p.national_id
            WHERE DATE(e.timestamp) >= DATE('now', '-7 days')
            AND p.village != ''
            GROUP BY p.village, e.symptoms_english
            HAVING case_count >= 2
            ORDER BY case_count DESC
            LIMIT 10
        """).fetchall()

    stats = {
        'total_patients':    total_patients,
        'total_encounters':  total_encounters,
        'high_risk':         high_risk,
        'medium_risk':       medium_risk,
        'low_risk':          low_risk,
        'total_referrals':   total_referrals,
        'total_escalations': total_escalations,
        'active_chws':       active_chws,
        'villages_covered':  villages_covered,
        'new_today':         new_today,
    }

    registry_stats = {
        'total_encounters':  total_encounters,
        'high_risk':         high_risk,
        'medium_risk':       medium_risk,
        'low_risk':          low_risk,
        'total_referrals':   total_referrals,
        'total_escalations': total_escalations,
        'active_chws':       active_chws,
        'villages_covered':  villages_covered,
        'top_villages':      [r['village'] for r in top_villages],
    }

    return render_template('dashboard_dho.html',
        stats=stats,
        facilities=facilities,
        top_villages=top_villages,
        disease_trends=disease_trends,
        chw_performance=chw_performance,
        outbreak_watch=outbreak_watch,
        registry_stats=registry_stats
    )


@dho_bp.route('/api/intelligence', methods=['GET'])
@role_required('DHO')
def get_intelligence():
    with get_db() as conn:
        total_encounters = conn.execute(
            "SELECT COUNT(*) FROM encounters"
        ).fetchone()[0]

        high_risk = conn.execute(
            "SELECT COUNT(*) FROM encounters WHERE risk_level = 'HIGH'"
        ).fetchone()[0]

        medium_risk = conn.execute(
            "SELECT COUNT(*) FROM encounters WHERE risk_level = 'MEDIUM'"
        ).fetchone()[0]

        low_risk = conn.execute(
            "SELECT COUNT(*) FROM encounters WHERE risk_level = 'LOW'"
        ).fetchone()[0]

        total_referrals = conn.execute(
            "SELECT COUNT(*) FROM encounters WHERE referral_needed = 1"
        ).fetchone()[0]

        total_escalations = conn.execute(
            "SELECT COUNT(*) FROM encounters WHERE escalated_to_supervisor = 1"
        ).fetchone()[0]

        active_chws = conn.execute(
            "SELECT COUNT(*) FROM users WHERE role = 'CHW' AND status = 'ACTIVE'"
        ).fetchone()[0]

        villages_covered = conn.execute(
            "SELECT COUNT(DISTINCT village) FROM patients WHERE village != ''"
        ).fetchone()[0]

        top_villages = [r['village'] for r in conn.execute("""
            SELECT village FROM patients
            WHERE village != ''
            GROUP BY village
            ORDER BY COUNT(*) DESC
            LIMIT 5
        """).fetchall()]

        facilities = [dict(row) for row in conn.execute(
            "SELECT * FROM facilities ORDER BY name"
        ).fetchall()]

    registry_stats = {
        'total_encounters':  total_encounters,
        'high_risk':         high_risk,
        'medium_risk':       medium_risk,
        'low_risk':          low_risk,
        'total_referrals':   total_referrals,
        'total_escalations': total_escalations,
        'active_chws':       active_chws,
        'villages_covered':  villages_covered,
        'top_villages':      top_villages,
    }

    try:
        result = generate_dho_intelligence(
            district="Lilongwe",
            registry_stats=registry_stats,
            clinic_registry=facilities
        )
        return jsonify(result)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@dho_bp.route('/api/update-facility', methods=['POST'])
@role_required('DHO')
def update_facility():
    data = request.json
    try:
        with get_db() as conn:
            conn.execute("""
                UPDATE facilities
                SET beds_available = ?,
                    blood_stock    = ?,
                    maternity_beds = ?,
                    status         = ?
                WHERE id = ?
            """, (
                int(data.get('beds_available', 0)),
                data.get('blood_stock', 'Available'),
                int(data.get('maternity_beds', 0)),
                data.get('status', 'ACTIVE'),
                data.get('facility_id')
            ))
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500