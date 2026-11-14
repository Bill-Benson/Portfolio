import os
import re
import hmac
import time
from datetime import date, datetime
from functools import wraps

import pyotp
from flask import (Blueprint, render_template, request, session, redirect, url_for, abort,
                   current_app, flash)
from werkzeug.security import check_password_hash

import content
import storage
from extensions import limiter

bp = Blueprint('admin', __name__, url_prefix='/admin')

# A login lasts at most this long, however active the session is. The idle
# timeout is PERMANENT_SESSION_LIFETIME, set in server.py.
SESSION_MAX_AGE = 8 * 60 * 60
MAX_PASSWORD_LENGTH = 256
MAX_BODY_LENGTH = 200_000
CODE_RE = re.compile(r'^[0-9]{6}$')

# Time step of the last accepted TOTP code, so a code can't be used twice.
_last_totp_step = 0


def admin_configured():
    return bool(os.environ.get('ADMIN_PASSWORD_HASH') and os.environ.get('ADMIN_TOTP_SECRET'))


def is_admin():
    logged_in_at = session.get('admin_at')
    return bool(admin_configured() and logged_in_at and time.time() - logged_in_at <= SESSION_MAX_AGE)


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
    # Not 'no-referrer': over https Flask-WTF rejects a form post that has no
    # Referer header, and the admin's own forms need to pass that check.
    response.headers['Referrer-Policy'] = 'same-origin'
    return response


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not is_admin():
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
    return render_template(
        'admin/dashboard.html',
        posts=content.load_posts(include_drafts=True),
        github_repo=os.environ.get('GITHUB_REPO') if storage.github_configured() else None,
    )


# Posts

def slugify(title):
    return re.sub(r'[^a-z0-9]+', '-', title.lower()).strip('-')[:80]


def read_post_form():
    def one_line(name, limit):
        # Front matter is one 'key: value' per line, so no line breaks.
        return ' '.join(request.form.get(name, '').split())[:limit]
    return {
        'slug': request.form.get('slug', '').strip().lower(),
        'title': one_line('title', 200),
        'date': one_line('date', 10),
        'description': one_line('description', 500),
        'tags': one_line('tags', 200),
        'draft': bool(request.form.get('draft')),
        'body': request.form.get('body', '').replace('\r\n', '\n')[:MAX_BODY_LENGTH],
    }


def validate_post_form(form):
    errors = []
    if not form['title']:
        errors.append('Title is required.')
    try:
        datetime.strptime(form['date'], '%Y-%m-%d')
    except ValueError:
        errors.append('Date must be in the form YYYY-MM-DD.')
    if not form['body'].strip():
        errors.append('The post body is empty.')
    return errors


def save_post(slug, form, meta, message):
    """Write the form over the post's existing front matter and save it."""
    meta = dict(meta)
    for field in ('title', 'date', 'description', 'tags'):
        meta[field] = form[field]
    meta['draft'] = 'true' if form['draft'] else ''
    text = content.build_post(meta, form['body'])
    storage.save_file(f'posts/{slug}.md', text.encode('utf-8'), message)


def flash_saved(what):
    if storage.github_configured():
        flash(f'{what} The live site updates in a minute or two.')
    else:
        flash(f'{what} Saved on this machine only.')


def render_post_form(form, errors, new, status=200):
    return render_template(
        'admin/post_form.html',
        form=form, errors=errors, new=new,
        preview_html=content.render_markdown(form['body']),
    ), status


@bp.route('/posts/new', methods=['GET', 'POST'])
@login_required
def post_new():
    if request.method == 'GET':
        form = {'slug': '', 'title': '', 'date': date.today().isoformat(), 'description': '',
                'tags': '', 'draft': True, 'body': ''}
        return render_post_form(form, [], new=True)

    form = read_post_form()
    form['slug'] = form['slug'] or slugify(form['title'])
    errors = validate_post_form(form)
    if not content.SLUG_RE.fullmatch(form['slug']):
        errors.append('The URL name can only contain lowercase letters, numbers and hyphens.')
    elif os.path.isfile(content.post_path(form['slug'])):
        errors.append('A post with that URL name already exists.')
    if errors:
        return render_post_form(form, errors, new=True, status=400)

    try:
        save_post(form['slug'], form, {}, f"Add post: {form['title']}")
    except storage.StorageError as error:
        return render_post_form(form, [str(error)], new=True, status=502)
    flash_saved('Post created.')
    return redirect(url_for('admin.post_edit', slug=form['slug']))


@bp.route('/posts/<slug>', methods=['GET', 'POST'])
@login_required
def post_edit(slug):
    source = content.read_post_source(slug) if content.SLUG_RE.fullmatch(slug) else None
    if source is None:
        abort(404)
    meta, body = source

    if request.method == 'GET':
        form = {'slug': slug, 'title': meta.get('title', ''), 'date': meta.get('date', ''),
                'description': meta.get('description', ''), 'tags': meta.get('tags', ''),
                'draft': meta.get('draft', '').lower() == 'true', 'body': body.strip() + '\n'}
        return render_post_form(form, [], new=False)

    form = read_post_form()
    form['slug'] = slug
    errors = validate_post_form(form)
    if errors:
        return render_post_form(form, errors, new=False, status=400)

    try:
        save_post(slug, form, meta, f"Update post: {form['title']}")
    except storage.StorageError as error:
        return render_post_form(form, [str(error)], new=False, status=502)
    flash_saved('Post saved.')
    return redirect(url_for('admin.post_edit', slug=slug))


@bp.route('/posts/<slug>/delete', methods=['POST'])
@login_required
def post_delete(slug):
    if not content.SLUG_RE.fullmatch(slug) or not os.path.isfile(content.post_path(slug)):
        abort(404)
    try:
        storage.delete_file(f'posts/{slug}.md', f'Delete post: {slug}')
    except storage.StorageError as error:
        flash(str(error))
        return redirect(url_for('admin.post_edit', slug=slug))
    flash_saved('Post deleted.')
    return redirect(url_for('admin.dashboard'))


@bp.route('/preview', methods=['POST'])
@login_required
def preview():
    return content.render_markdown(request.form.get('body', '')[:MAX_BODY_LENGTH])
