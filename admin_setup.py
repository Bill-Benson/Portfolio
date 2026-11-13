"""Generate the admin login credentials: a password hash and a TOTP secret.

Run it once, add the two values it prints to .env (and to Render's
environment variables), and add the TOTP secret to an authenticator app.
"""
import getpass

import pyotp
from werkzeug.security import generate_password_hash

MIN_PASSWORD_LENGTH = 12


def main():
    password = getpass.getpass(f'New admin password ({MIN_PASSWORD_LENGTH}+ characters): ')
    if len(password) < MIN_PASSWORD_LENGTH:
        raise SystemExit(f'Password must be at least {MIN_PASSWORD_LENGTH} characters.')
    if getpass.getpass('Repeat password: ') != password:
        raise SystemExit('Passwords did not match.')

    secret = pyotp.random_base32()
    uri = pyotp.TOTP(secret).provisioning_uri(name='admin', issuer_name='Bill Benson Portfolio')

    print('\nAdd these two lines to .env (keep the single quotes):\n')
    print(f"ADMIN_PASSWORD_HASH='{generate_password_hash(password)}'")
    print(f"ADMIN_TOTP_SECRET='{secret}'")
    print('\nOn Render, add the same two variables without the quotes.')
    print('\nIn your authenticator app, add an account by setup key:')
    print(f'  Key:  {secret}')
    print('  Type: time-based')
    print(f'\nOr turn this link into a QR code and scan it:\n  {uri}')


if __name__ == '__main__':
    main()
