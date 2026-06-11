import os
import re
import csv
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from flask import Flask, render_template, request, abort
from flask_wtf.csrf import CSRFProtect
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from dotenv import load_dotenv
import markdown2

load_dotenv()

app = Flask(__name__, static_folder='static')
app.config['SECRET_KEY'] = os.environ['SECRET_KEY']

csrf = CSRFProtect(app)
limiter = Limiter(get_remote_address, app=app, default_limits=[])


POSTS_DIR = os.path.join(os.path.dirname(__file__), 'posts')


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
    meta['html'] = markdown2.markdown(body, extras=['fenced-code-blocks', 'tables', 'strike'])
    return meta


def load_posts():
    posts = []
    if not os.path.isdir(POSTS_DIR):
        return posts
    for filename in sorted(os.listdir(POSTS_DIR), reverse=True):
        if filename.endswith('.md'):
            slug = filename[:-3]
            meta = parse_post(os.path.join(POSTS_DIR, filename))
            meta['slug'] = slug
            posts.append(meta)
    return posts


@app.route('/')
def hello_world():
    return render_template("index.html")


@app.route('/blog')
def blog_index():
    posts = load_posts()
    return render_template("blog.html", posts=posts)


@app.route('/blog/<slug>')
def blog_post(slug):
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
