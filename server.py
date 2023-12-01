from flask import Flask, render_template, request
import csv
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart


app = Flask(__name__, static_folder='static')


@app.route('/')
def hello_world():
    return render_template("index.html")


@app.route('/submit_form', methods=['POST', 'GET'])
def submit_form():
    if request.method == 'POST':
        data = request.form.to_dict()
        write_to_csv(data)
        send_email(data)
        return render_template('thanks.html')


def write_to_file(data):
    with open("database.txt", mode="a") as database:
        email = data["email"]
        name = data["name"]
        message = data["message"]
        database.write(f"\n{email}, {name}, {message}")


def write_to_csv(data):
    with open("database.csv", mode="a") as database2:
        email = data["email"]
        name = data["name"]
        message = data["message"]
        csv_data = csv.writer(database2, delimiter="|", quotechar='"', quoting=csv.QUOTE_MINIMAL)
        csv_data.writerow([name, email, message])


def send_email(data):
    sender_email = "1stdiscordlove@gmail.com"  # Replace with your email
    sender_password = "agdh lmmj ktvl ktqg"  # Replace with your email password
    recipient_email = "billbenson886@gmail.com"  # Replace with the recipient's email

    subject = "From Your Portfolio Website"
    body = f"Name: {data['name']}\nEmail: {data['email']}\nMessage: {data['message']}"

    # Create the MIME object
    msg = MIMEMultipart()
    msg.attach(MIMEText(body, 'plain'))
    msg['From'] = sender_email
    msg['To'] = recipient_email
    msg['Subject'] = subject

    # Connect to the SMTP server and send the email
    with smtplib.SMTP('smtp.gmail.com', 587) as server:
        server.starttls()
        server.login(sender_email, sender_password)
        server.sendmail(sender_email, recipient_email, msg.as_string())


if __name__ == '__main__':
    app.run()
