from flask import (Blueprint, render_template, request,
                   redirect, url_for, session, flash, jsonify)
from database import get_db, hash_password
from routes.auth import role_required

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')


# ── Admin Home Dashboard ───────────────────────────────────────────────────
@admin_bp.route('/')
@role_required('ADMIN')
def dashboard():
    with get_db() as conn:
        total_users = conn.execute(
            "SELECT COUNT(*) FROM users WHERE role != 'ADMIN'"
        ).fetchone()[0]

        total_chws = conn.execute(
            "SELECT COUNT(*) FROM users WHERE role = 'CHW' AND status = 'ACTIVE'"
        ).fetchone()[0]

        total_supervisors = conn.execute(
            "SELECT COUNT(*) FROM users WHERE role = 'SUPERVISOR' AND status = 'ACTIVE'"
        ).fetchone()[0]

        total_dhos = conn.execute(
            "SELECT COUNT(*) FROM users WHERE role = 'DHO' AND status = 'ACTIVE'"
        ).fetchone()[0]

        total_patients = conn.execute(
            "SELECT COUNT(*) FROM patients"
        ).fetchone()[0]

        total_encounters = conn.execute(
            "SELECT COUNT(*) FROM encounters"
        ).fetchone()[0]

        high_risk = conn.execute(
            "SELECT COUNT(*) FROM encounters WHERE risk_level = 'HIGH'"
        ).fetchone()[0]

        total_referrals = conn.execute(
            "SELECT COUNT(*) FROM encounters WHERE referral_needed = 1"
        ).fetchone()[0]

        facilities = conn.execute(
            "SELECT * FROM facilities ORDER BY name"
        ).fetchall()

        recent_users = conn.execute("""
            SELECT u.id, u.username, u.full_name, u.role,
                   u.catchment_area, u.status, u.created_at,
                   f.name as facility_name
            FROM users u
            LEFT JOIN facilities f ON u.facility_id = f.id
            WHERE u.role != 'ADMIN'
            ORDER BY u.created_at DESC
            LIMIT 10
        """).fetchall()

    stats = {
        'total_users': total_users,
        'total_chws': total_chws,
        'total_supervisors': total_supervisors,
        'total_dhos': total_dhos,
        'total_patients': total_patients,
        'total_encounters': total_encounters,
        'high_risk': high_risk,
        'total_referrals': total_referrals,
    }

    return render_template('admin_dashboard.html',
                           stats=stats,
                           facilities=facilities,
                           recent_users=recent_users)


# ── Register New Worker ────────────────────────────────────────────────────
@admin_bp.route('/register', methods=['GET', 'POST'])
@role_required('ADMIN')
def register_worker():
    with get_db() as conn:
        facilities = conn.execute(
            "SELECT id, name, location FROM facilities ORDER BY name"
        ).fetchall()

    error = None
    success = None

    if request.method == 'POST':
        username      = request.form.get('username', '').strip()
        password      = request.form.get('password', '').strip()
        full_name     = request.form.get('full_name', '').strip()
        role          = request.form.get('role', '').strip()
        catchment     = request.form.get('catchment_area', '').strip()
        facility_id   = request.form.get('facility_id', '').strip()

        # ── Validation ────────────────────────────────────────────────────
        if not all([username, password, full_name, role]):
            error = 'Username, password, full name, and role are required.'
        elif role not in ['CHW', 'SUPERVISOR', 'DHO']:
            error = 'Invalid role selected.'
        elif len(password) < 8:
            error = 'Password must be at least 8 characters.'
        else:
            facility_id = int(facility_id) if facility_id else None
            try:
                with get_db() as conn:
                    conn.execute("""
                        INSERT INTO users
                            (username, password_hash, full_name, role,
                             catchment_area, facility_id, status)
                        VALUES (?, ?, ?, ?, ?, ?, 'ACTIVE')
                    """, (
                        username,
                        hash_password(password),
                        full_name,
                        role,
                        catchment,
                        facility_id
                    ))
                success = (f"Worker '{full_name}' registered successfully "
                           f"as {role} with username '{username}'.")
            except Exception as e:
                if 'UNIQUE constraint failed' in str(e):
                    error = f"Username '{username}' is already taken."
                else:
                    error = f"Registration failed: {str(e)}"

    return render_template('admin_register.html',
                           facilities=facilities,
                           error=error,
                           success=success)


# ── List All Workers ───────────────────────────────────────────────────────
@admin_bp.route('/workers')
@role_required('ADMIN')
def list_workers():
    role_filter   = request.args.get('role', 'ALL')
    status_filter = request.args.get('status', 'ALL')

    query = """
        SELECT u.id, u.username, u.full_name, u.role,
               u.catchment_area, u.status, u.created_at,
               f.name as facility_name
        FROM users u
        LEFT JOIN facilities f ON u.facility_id = f.id
        WHERE u.role != 'ADMIN'
    """
    params = []

    if role_filter != 'ALL':
        query += " AND u.role = ?"
        params.append(role_filter)

    if status_filter != 'ALL':
        query += " AND u.status = ?"
        params.append(status_filter)

    query += " ORDER BY u.role, u.full_name"

    with get_db() as conn:
        workers = conn.execute(query, params).fetchall()

    return render_template('admin_workers.html',
                           workers=workers,
                           role_filter=role_filter,
                           status_filter=status_filter)


# ── Toggle Worker Status ───────────────────────────────────────────────────
@admin_bp.route('/worker/<int:worker_id>/toggle', methods=['POST'])
@role_required('ADMIN')
def toggle_worker(worker_id):
    with get_db() as conn:
        user = conn.execute(
            "SELECT id, full_name, status, role FROM users WHERE id = ?",
            (worker_id,)
        ).fetchone()

        if not user:
            flash('Worker not found.', 'danger')
            return redirect(url_for('admin.list_workers'))

        if user['role'] == 'ADMIN':
            flash('Cannot modify admin accounts.', 'danger')
            return redirect(url_for('admin.list_workers'))

        new_status = 'SUSPENDED' if user['status'] == 'ACTIVE' else 'ACTIVE'
        conn.execute(
            "UPDATE users SET status = ? WHERE id = ?",
            (new_status, worker_id)
        )

    action = 'suspended' if new_status == 'SUSPENDED' else 'reactivated'
    flash(f"{user['full_name']} has been {action}.", 'success')
    return redirect(url_for('admin.list_workers'))


# ── Facility Management ────────────────────────────────────────────────────
@admin_bp.route('/facilities')
@role_required('ADMIN')
def facilities():
    with get_db() as conn:
        facs = conn.execute(
            "SELECT * FROM facilities ORDER BY name"
        ).fetchall()
    return render_template('admin_facilities.html', facilities=facs)


@admin_bp.route('/facility/update', methods=['POST'])
@role_required('ADMIN')
def update_facility():
    facility_id    = request.form.get('facility_id')
    beds_available = request.form.get('beds_available', 0)
    blood_stock    = request.form.get('blood_stock', 'Available')
    maternity_beds = request.form.get('maternity_beds', 0)
    status         = request.form.get('status', 'ACTIVE')

    try:
        with get_db() as conn:
            conn.execute("""
                UPDATE facilities
                SET beds_available = ?,
                    blood_stock    = ?,
                    maternity_beds = ?,
                    status         = ?
                WHERE id = ?
            """, (beds_available, blood_stock, maternity_beds,
                  status, facility_id))
        flash('Facility updated successfully.', 'success')
    except Exception as e:
        flash(f'Update failed: {str(e)}', 'danger')

    return redirect(url_for('admin.facilities'))


# ── API: System stats for dashboard refresh ────────────────────────────────
@admin_bp.route('/api/stats')
@role_required('ADMIN')
def api_stats():
    with get_db() as conn:
        stats = {
            'total_patients': conn.execute(
                "SELECT COUNT(*) FROM patients").fetchone()[0],
            'total_encounters': conn.execute(
                "SELECT COUNT(*) FROM encounters").fetchone()[0],
            'high_risk': conn.execute(
                "SELECT COUNT(*) FROM encounters WHERE risk_level = 'HIGH'"
            ).fetchone()[0],
            'active_chws': conn.execute(
                "SELECT COUNT(*) FROM users WHERE role='CHW' AND status='ACTIVE'"
            ).fetchone()[0],
        }
    return jsonify(stats)