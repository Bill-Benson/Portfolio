import os
import re
import csv
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from flask import Flask, render_template, request
from flask_wtf.csrf import CSRFProtect
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__, static_folder='static')
app.config['SECRET_KEY'] = os.environ['SECRET_KEY']

csrf = CSRFProtect(app)
limiter = Limiter(get_remote_address, app=app, default_limits=[])


@app.route('/')
def hello_world():
    return render_template("index.html")


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
