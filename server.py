import os
import re
import csv
import smtplib
from datetime import timedelta
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from flask import Flask, render_template, request, abort
from dotenv import load_dotenv
from markupsafe import Markup, escape

from extensions import csrf, limiter
from admin import bp as admin_bp, is_admin
import admin_content  # adds the homepage editor routes to the admin blueprint
import admin_uploads  # and the upload routes
from content import CONTENT_SECTIONS, SLUG_RE, load_content, load_posts, parse_post, post_path

load_dotenv()

app = Flask(__name__, static_folder='static')
app.config['SECRET_KEY'] = os.environ['SECRET_KEY']
app.config.update(
    # Render sets RENDER=true; locally the site runs over plain http, where a
    # Secure cookie would never be sent back.
    SESSION_COOKIE_SECURE=bool(os.environ.get('RENDER')),
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE='Lax',
    # Idle timeout for the admin session.
    PERMANENT_SESSION_LIFETIME=timedelta(minutes=30),
    # Hard cap on request size; uploads apply their own lower limit.
    MAX_CONTENT_LENGTH=8 * 1024 * 1024,
)

csrf.init_app(app)
limiter.init_app(app)
app.register_blueprint(admin_bp)


@app.template_filter('inline_md')
def inline_md(text):
    # Content files hold plain text; the only markup allowed is **bold**.
    # Escape first so nothing else in the text can reach the page as HTML.
    return Markup(re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', str(escape(text))))


@app.route('/')
def hello_world():
    content = {name: load_content(name) for name in CONTENT_SECTIONS}
    posts = load_posts()
    return render_template("index.html", latest_post=posts[0] if posts else None, **content)


@app.route('/blog')
def blog_index():
    posts = load_posts()
    return render_template("blog.html", posts=posts)


@app.route('/blog/<slug>')
def blog_post(slug):
    if not SLUG_RE.match(slug):
        abort(404)
    filepath = post_path(slug)
    if not os.path.isfile(filepath):
        abort(404)
    meta = parse_post(filepath)
    # Drafts exist only for the logged-in admin, as a preview.
    if meta['is_draft'] and not is_admin():
        abort(404)
    meta['slug'] = slug
    return render_template("blog_post.html", post=meta)


@app.route('/submit_form', methods=['POST'])
@limiter.limit("5 per hour")
def submit_form():
    name = request.form.get('name', '').strip()
    email = request.form.get('email', '').strip()
    message = request.form.get('message', '').strip()

    if not name or not email or not message:
        return render_template('service_unavailable.html'), 400

    if not re.match(r'^[^@\s]+@[^@\s]+\.[^@\s]+$', email):
        return render_template('service_unavailable.html'), 400

    if len(name) > 100 or len(email) > 254 or len(message) > 2000:
        return render_template('service_unavailable.html'), 400

    data = {'name': name, 'email': email, 'message': message}
    write_to_csv(data)

    try:
        send_email(data)
    except Exception:
        pass

    return render_template('thanks.html')


def write_to_csv(data):
    with open("database.csv", mode="a", newline='') as database:
        writer = csv.writer(database, delimiter="|", quotechar='"', quoting=csv.QUOTE_ALL)
        writer.writerow([data['name'], data['email'], data['message']])


def send_email(data):
    sender_email = os.environ['SENDER_EMAIL']
    sender_password = os.environ['SENDER_PASSWORD']
    recipient_email = os.environ.get('RECIPIENT_EMAIL', sender_email)

    msg = MIMEMultipart()
    msg['From'] = sender_email
    msg['To'] = recipient_email
    msg['Subject'] = "From Your Portfolio Website"
    msg.attach(MIMEText(
        f"Name: {data['name']}\nEmail: {data['email']}\nMessage: {data['message']}",
        'plain'
    ))

    with smtplib.SMTP('smtp.gmail.com', 587) as server:
        server.starttls()
        server.login(sender_email, sender_password)
        server.sendmail(sender_email, recipient_email, msg.as_string())


if __name__ == '__main__':
    app.run()
