import os
import re
import json
from datetime import datetime

import markdown2

ROOT = os.path.dirname(os.path.abspath(__file__))
POSTS_DIR = os.path.join(ROOT, 'posts')
CONTENT_DIR = os.path.join(ROOT, 'content')
# Homepage sections, each stored as content/<name>.json.
CONTENT_SECTIONS = ('profile', 'experience', 'projects', 'skills', 'certifications', 'about')

SLUG_RE = re.compile(r'^[a-z0-9-]+$')


def load_content(name):
    with open(os.path.join(CONTENT_DIR, f'{name}.json'), encoding='utf-8') as f:
        return json.load(f)


def render_markdown(body):
    return markdown2.markdown(body, extras=['fenced-code-blocks', 'tables', 'strike'])


def split_post(text):
    """Split a post file into its front matter (a dict) and its markdown body."""
    meta = {}
    body = text
    if text.startswith('---'):
        parts = text.split('---', 2)
        if len(parts) == 3:
            for line in parts[1].strip().splitlines():
                key, _, value = line.partition(': ')
                meta[key.strip()] = value.strip()
            body = parts[2]
    return meta, body


def build_post(meta, body):
    """The reverse of split_post: front matter and body back into file text."""
    lines = [f'{key}: {value}' for key, value in meta.items() if value]
    return '---\n' + '\n'.join(lines) + '\n---\n\n' + body.strip() + '\n'


def post_path(slug):
    return os.path.join(POSTS_DIR, f'{slug}.md')


def read_post_source(slug):
    """Return (front matter, body) for a post, or None if it doesn't exist."""
    filepath = post_path(slug)
    if not os.path.isfile(filepath):
        return None
    with open(filepath, encoding='utf-8') as f:
        return split_post(f.read())


def parse_post(filepath):
    with open(filepath, encoding='utf-8') as f:
        meta, body = split_post(f.read())
    # 'date' is stored as ISO (YYYY-MM-DD) for reliable sorting; expose a
    # human-readable 'date_display' for templates.
    iso = meta.get('date', '')
    try:
        meta['date_display'] = datetime.strptime(iso, '%Y-%m-%d').strftime('%d %B %Y').lstrip('0')
    except ValueError:
        meta['date_display'] = iso
    # Drafts ('draft: true' in the front matter) are only shown to the admin.
    meta['is_draft'] = meta.get('draft', '').lower() == 'true'
    meta['html'] = render_markdown(body)
    return meta


def load_posts(include_drafts=False):
    posts = []
    if not os.path.isdir(POSTS_DIR):
        return posts
    for filename in os.listdir(POSTS_DIR):
        if filename.endswith('.md'):
            meta = parse_post(os.path.join(POSTS_DIR, filename))
            meta['slug'] = filename[:-3]
            if include_drafts or not meta['is_draft']:
                posts.append(meta)
    # Newest first, ordered by the ISO date field rather than filename.
    posts.sort(key=lambda p: p.get('date', ''), reverse=True)
    return posts
