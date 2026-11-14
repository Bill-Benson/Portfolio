"""Saving edits made in the admin.

Render's disk is wiped on every deploy, so a file written there doesn't
last. Each save is committed to the GitHub repo through the contents API,
which triggers a redeploy, and is also written to the local disk so the
running site shows the change straight away. Without a GitHub token (local
development) only the local write happens.
"""
import os
import json
import base64
import urllib.error
import urllib.parse
import urllib.request

import content

API_URL = 'https://api.github.com'
# The only places the admin may write to, relative to the repo root.
WRITABLE_PREFIXES = ('posts/', 'content/', 'static/images/')
WRITABLE_FILES = ('static/assets/Bill_Benson_CV.pdf',)


class StorageError(Exception):
    pass


def github_configured():
    return bool(os.environ.get('GITHUB_TOKEN') and os.environ.get('GITHUB_REPO'))


def _branch():
    return os.environ.get('GITHUB_BRANCH', 'main')


def _check_path(path):
    if os.path.normpath(path).replace(os.sep, '/') != path or not (path.startswith(WRITABLE_PREFIXES) or path in WRITABLE_FILES):
        raise StorageError(f'Refusing to write outside the content folders: {path}')


def _require_durable_storage():
    # On Render a local-only write would look saved and then vanish.
    if os.environ.get('RENDER') and not github_configured():
        raise StorageError('GitHub saving is not set up: add GITHUB_TOKEN and GITHUB_REPO on Render.')


def _github_reason(error):
    """GitHub's own explanation from an error response, as ': reason', or '.'."""
    try:
        message = json.load(error).get('message')
    except Exception:
        message = None
    return f': {message}' if message else '.'


def _github(method, path, payload=None):
    url = f"{API_URL}/repos/{os.environ['GITHUB_REPO']}/contents/{urllib.parse.quote(path)}"
    if method == 'GET':
        url += '?ref=' + urllib.parse.quote(_branch())
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode() if payload else None,
        method=method,
        headers={
            'Authorization': f"Bearer {os.environ['GITHUB_TOKEN']}",
            'Accept': 'application/vnd.github+json',
            'X-GitHub-Api-Version': '2022-11-28',
            'User-Agent': 'portfolio-admin',
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            return json.load(response)
    except urllib.error.HTTPError as error:
        if method == 'GET' and error.code == 404:
            return None
        raise StorageError(f'GitHub rejected the change (HTTP {error.code}){_github_reason(error)}') from error
    except (urllib.error.URLError, TimeoutError) as error:
        raise StorageError('Could not reach GitHub.') from error


def save_file(path, data, message):
    """Write bytes to a repo-relative path, committing with the given message."""
    _check_path(path)
    _require_durable_storage()
    if github_configured():
        payload = {
            'message': message,
            'content': base64.b64encode(data).decode(),
            'branch': _branch(),
        }
        existing = _github('GET', path)
        if existing:
            payload['sha'] = existing['sha']
        _github('PUT', path, payload)
    local_path = os.path.join(content.ROOT, path)
    os.makedirs(os.path.dirname(local_path), exist_ok=True)
    with open(local_path, 'wb') as f:
        f.write(data)


def delete_file(path, message):
    _check_path(path)
    _require_durable_storage()
    if github_configured():
        existing = _github('GET', path)
        if existing:
            _github('DELETE', path, {'message': message, 'sha': existing['sha'], 'branch': _branch()})
    local_path = os.path.join(content.ROOT, path)
    if os.path.isfile(local_path):
        os.remove(local_path)
