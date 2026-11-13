import os
import re
import hmac
import time
from functools import wraps

import pyotp
from flask import Blueprint, render_template, request, session, redirect, url_for, abort, current_app
from werkzeug.security import check_password_hash

from extensions import limiter

bp = Blueprint('admin', __name__, url_prefix='/admin')

# A login lasts at most this long, however active the session is. The idle
# timeout is PERMANENT_SESSION_LIFETIME, set in server.py.
SESSION_MAX_AGE = 8 * 60 * 60
MAX_PASSWORD_LENGTH = 256
CODE_RE = re.compile(r'^[0-9]{6}$')

# Time step of the last accepted TOTP code, so a code can't be used twice.
_last_totp_step = 0


def admin_configured():
    return bool(os.environ.get('ADMIN_PASSWORD_HASH') and os.environ.get('ADMIN_TOTP_SECRET'))


@bp.before_request
def require_configured():
    # Without credentials in the environment the admin doesn't exist at all.
    if not admin_configured():
        abort(404)


@bp.after_request
def harden_response(response):
    response.headers['Cache-Control'] = 'no-store'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['Referrer-Policy'] = 'no-referrer'
    return response


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        logged_in_at = session.get('admin_at')
        if not logged_in_at or time.time() - logged_in_at > SESSION_MAX_AGE:
            session.clear()
            return redirect(url_for('admin.login'))
        return view(*args, **kwargs)
    return wrapped


def matching_totp_step(code):
    """Return the time step the code is valid for, or None."""
    if not CODE_RE.match(code):
        return None
    totp = pyotp.TOTP(os.environ['ADMIN_TOTP_SECRET'])
    now = time.time()
    # Accept the previous and next step too, to allow for clock drift.
    for offset in (-1, 0, 1):
        step = int(now) // 30 + offset
        if step > _last_totp_step and hmac.compare_digest(totp.at(now, offset), code):
            return step
    return None


@bp.route('/login', methods=['GET', 'POST'])
@limiter.limit("5 per 15 minutes", methods=['POST'])
def login():
    global _last_totp_step
    if request.method == 'GET':
        return render_template('admin/login.html', error=None)

    password = request.form.get('password', '')[:MAX_PASSWORD_LENGTH]
    code = request.form.get('code', '').strip()

    # Check both factors every time and report one generic error, so a
    # failed attempt doesn't reveal which of the two was wrong.
    password_ok = check_password_hash(os.environ['ADMIN_PASSWORD_HASH'], password)
    step = matching_totp_step(code)
    if not (password_ok and step):
        current_app.logger.warning('Failed admin login from %s', request.remote_addr)
        return render_template('admin/login.html', error='Incorrect password or code.'), 401

    _last_totp_step = step
    session.clear()
    session.permanent = True
    session['admin_at'] = time.time()
    current_app.logger.info('Admin login from %s', request.remote_addr)
    return redirect(url_for('admin.dashboard'))


@bp.route('/logout', methods=['POST'])
def logout():
    session.clear()
    return redirect(url_for('admin.login'))


@bp.route('/')
@login_required
def dashboard():
    return render_template('admin/dashboard.html')
