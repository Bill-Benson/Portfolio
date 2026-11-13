import os
import re
import csv
import json
import smtplib
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from flask import Flask, render_template, request, abort
from flask_wtf.csrf import CSRFProtect
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from dotenv import load_dotenv
from markupsafe import Markup, escape
import markdown2

SLUG_RE = re.compile(r'^[a-z0-9-]+$')

load_dotenv()

app = Flask(__name__, static_folder='static')
app.config['SECRET_KEY'] = os.environ['SECRET_KEY']

csrf = CSRFProtect(app)
limiter = Limiter(get_remote_address, app=app, default_limits=[])


POSTS_DIR = os.path.join(os.path.dirname(__file__), 'posts')
CONTENT_DIR = os.path.join(os.path.dirname(__file__), 'content')
# Homepage sections, each stored as content/<name>.json.
CONTENT_SECTIONS = ('profile', 'experience', 'projects', 'skills', 'certifications', 'about')


def load_content(name):
    with open(os.path.join(CONTENT_DIR, f'{name}.json'), encoding='utf-8') as f:
        return json.load(f)


@app.template_filter('inline_md')
def inline_md(text):
    # Content files hold plain text; the only markup allowed is **bold**.
    # Escape first so nothing else in the text can reach the page as HTML.
    return Markup(re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', str(escape(text))))


def parse_post(filepath):
    with open(filepath, encoding='utf-8') as f:
        content = f.read()
    meta = {}
    body = content
    if content.startswith('---'):
        parts = content.split('---', 2)
        if len(parts) == 3:
            for line in parts[1].strip().splitlines():
                key, _, value = line.partition(': ')
                meta[key.strip()] = value.strip()
            body = parts[2]
    # 'date' is stored as ISO (YYYY-MM-DD) for reliable sorting; expose a
    # human-readable 'date_display' for templates.
    iso = meta.get('date', '')
    try:
        meta['date_display'] = datetime.strptime(iso, '%Y-%m-%d').strftime('%d %B %Y').lstrip('0')
    except ValueError:
        meta['date_display'] = iso
    meta['html'] = markdown2.markdown(body, extras=['fenced-code-blocks', 'tables', 'strike'])
    return meta


def load_posts():
    posts = []
    if not os.path.isdir(POSTS_DIR):
        return posts
    for filename in os.listdir(POSTS_DIR):
        if filename.endswith('.md'):
            meta = parse_post(os.path.join(POSTS_DIR, filename))
            meta['slug'] = filename[:-3]
            posts.append(meta)
    # Newest first, ordered by the ISO date field rather than filename.
    posts.sort(key=lambda p: p.get('date', ''), reverse=True)
    return posts


@app.route('/')
def hello_world():
    content = {name: load_content(name) for name in CONTENT_SECTIONS}
    return render_template("index.html", **content)


@app.route('/blog')
def blog_index():
    posts = load_posts()
    return render_template("blog.html", posts=posts)


@app.route('/blog/<slug>')
def blog_post(slug):
    if not SLUG_RE.match(slug):
        abort(404)
    filepath = os.path.join(POSTS_DIR, f'{slug}.md')
    if not os.path.isfile(filepath):
        abort(404)
    meta = parse_post(filepath)
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
