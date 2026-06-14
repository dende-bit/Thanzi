from flask import (Blueprint, render_template, request,
                   redirect, url_for, session, flash, jsonify)
from database import get_db, hash_password

auth_bp = Blueprint('auth', __name__)


def login_required(f):
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            if request.is_json or '/api/' in request.path:
                return jsonify({'error': 'Session expired. Please log in again.'}), 401
            flash('Please log in to continue.', 'warning')
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated


def role_required(*roles):
    from functools import wraps
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            if 'user_id' not in session:
                if request.is_json or '/api/' in request.path:
                    return jsonify({'error': 'Session expired. Please log in again.'}), 401
                flash('Please log in to continue.', 'warning')
                return redirect(url_for('auth.login'))
            if session.get('role') not in roles:
                if request.is_json or '/api/' in request.path:
                    return jsonify({'error': 'Access denied.'}), 403
                flash('You do not have permission to access that page.', 'danger')
                return redirect(url_for('auth.dashboard'))
            return f(*args, **kwargs)
        return decorated
    return decorator


@auth_bp.route('/')
def index():
    if 'user_id' in session:
        return redirect(url_for('auth.dashboard'))
    return redirect(url_for('auth.login'))


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if 'user_id' in session:
        return redirect(url_for('auth.dashboard'))

    error = None

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()

        if not username or not password:
            error = 'Please enter both username and password.'
        else:
            with get_db() as conn:
                user = conn.execute("""
                    SELECT id, username, password_hash, full_name,
                           role, catchment_area, facility_id, status
                    FROM users
                    WHERE username = ?
                """, (username,)).fetchone()

            if not user:
                error = 'Username not found.'
            elif user['status'] != 'ACTIVE':
                error = 'Your account is suspended. Contact your administrator.'
            elif user['password_hash'] != hash_password(password):
                error = 'Incorrect password.'
            else:
                session.permanent = True
                session['user_id']        = user['id']
                session['username']       = user['username']
                session['full_name']      = user['full_name']
                session['role']           = user['role']
                session['catchment_area'] = user['catchment_area']
                session['facility_id']    = user['facility_id']
                return redirect(url_for('auth.dashboard'))

    return render_template('login.html', error=error)


@auth_bp.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out.', 'info')
    return redirect(url_for('auth.login'))


@auth_bp.route('/dashboard')
@login_required
def dashboard():
    role = session.get('role')
    if role == 'ADMIN':
        return redirect(url_for('auth.admin_home'))
    elif role == 'CHW':
        return redirect(url_for('auth.chw_home'))
    elif role == 'SUPERVISOR':
        return redirect(url_for('auth.supervisor_home'))
    elif role == 'DHO':
        return redirect(url_for('auth.dho_home'))
    else:
        session.clear()
        flash('Unknown role. Please contact your administrator.', 'danger')
        return redirect(url_for('auth.login'))


@auth_bp.route('/admin/home')
@role_required('ADMIN')
def admin_home():
    return redirect(url_for('admin.dashboard'))


@auth_bp.route('/chw/home')
@role_required('CHW')
def chw_home():
    return redirect(url_for('chw.dashboard'))


@auth_bp.route('/supervisor/home')
@role_required('SUPERVISOR')
def supervisor_home():
    return redirect(url_for('supervisor.dashboard'))


@auth_bp.route('/dho/home')
@role_required('DHO')
def dho_home():
    return redirect(url_for('dho.dashboard'))