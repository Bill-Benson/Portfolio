"""Homepage editors: one form per content/*.json section.

Every section is described by a list of fields, and one generic form
renders and saves all of them. A list section (projects, experience, ...)
shows every entry on one page, so a round of edits, reordering and
deletions is saved as a single commit.
"""
import os
import re
import json

from flask import render_template, request, redirect, url_for, abort, flash

import content
import storage
from admin import bp, login_required, flash_saved

MAX_FIELD_LENGTH = 5000
EMPTY = ('', [], None)


def check_link(value):
    if not re.fullmatch(r'(https?://|/)\S*', value):
        return 'must start with https:// or /'


def check_email(value):
    if not re.fullmatch(r'[^@\s]+@[^@\s]+\.[^@\s]+', value):
        return 'is not a valid email address'


def check_icon(value):
    if not re.fullmatch(r'fa[sbr] fa-[a-z0-9-]+', value):
        return 'must be a Font Awesome class such as "fas fa-bug"'


def check_image(value):
    if not re.fullmatch(r'images/[A-Za-z0-9_./-]+', value) or '..' in value:
        return 'must be a path such as images/projects/chart.png'
    if not os.path.isfile(os.path.join(content.ROOT, 'static', value)):
        return 'was not found in the static folder'


def field(name, label, kind='text', required=False, help=None, check=None):
    return {'name': name, 'label': label, 'kind': kind, 'required': required, 'help': help, 'check': check}


def finish_project(item, problems):
    """A featured card can't be drawn without its image; a standard one needs an icon."""
    if item.get('featured'):
        for name in ('image', 'image_alt', 'image_width', 'image_height'):
            if item.get(name) in EMPTY:
                problems.append(f'{name.replace("_", " ")} is required for a featured project')
    else:
        item.setdefault('icon', 'fas fa-code')


# 'file' is the content/<file>.json the section lives in; 'key' selects one
# value inside that file. The order of fields is the order keys are saved in.
SECTIONS = {
    'profile': {
        'title': 'Profile and links',
        'file': 'profile',
        'fields': [
            field('summary', 'hero summary', 'textarea', required=True, help='**bold** is allowed'),
            field('status', 'status badge', required=True),
            field('contact_intro', 'contact intro', 'textarea', required=True, help='**bold** is allowed'),
            field('email', 'email', required=True, check=check_email),
            field('github', 'github link', required=True, check=check_link),
            field('linkedin', 'linkedin link', required=True, check=check_link),
            field('cv', 'cv link', required=True, check=check_link, help='a web link, or /static/assets/Bill_Benson_CV.pdf'),
        ],
    },
    'experience': {
        'title': 'Experience',
        'file': 'experience',
        'list': True,
        'item_name': 'role',
        'label_field': 'title',
        'fields': [
            field('title', 'job title', required=True),
            field('period', 'period', required=True, help='e.g. Jul 2024 – Jan 2025'),
            field('org', 'organisation and location', required=True),
            field('bullets', 'bullet points', 'lines', required=True, help='one per line'),
        ],
    },
    'projects': {
        'title': 'Projects',
        'file': 'projects',
        'list': True,
        'item_name': 'project',
        'label_field': 'title',
        'finish': finish_project,
        'fields': [
            field('featured', 'Featured: large card with an image, shown first', 'bool'),
            field('title', 'title', required=True),
            field('label', 'label above the title', help='featured only, e.g. Featured · WAF Tuning'),
            field('image', 'image', check=check_image, help='featured only, a path inside static, e.g. images/projects/chart.png'),
            field('image_alt', 'image description for screen readers', help='featured only'),
            field('image_width', 'image width in pixels', 'int', help='featured only'),
            field('image_height', 'image height in pixels', 'int', help='featured only'),
            field('image_link_label', 'image link label', help='featured only, e.g. View full-size chart'),
            field('metric', 'headline result', help='featured only'),
            field('icon', 'icon', check=check_icon, help='standard cards only, e.g. fas fa-bug'),
            field('description', 'description', 'textarea', required=True),
            field('tags', 'tags', 'tags', help='comma separated'),
            field('source', 'source code link', check=check_link, help='optional'),
            field('writeup', 'write-up link', check=check_link, help='optional, e.g. /blog/my-post'),
        ],
    },
    'skills': {
        'title': 'Skills',
        'file': 'skills',
        'list': True,
        'item_name': 'skill group',
        'label_field': 'name',
        'fields': [
            field('name', 'group name', required=True),
            field('icon', 'icon', required=True, check=check_icon, help='e.g. fas fa-terminal'),
            field('items', 'skills', 'lines', required=True, help='one per line'),
        ],
    },
    'certifications': {
        'title': 'Certifications',
        'file': 'certifications',
        'list': True,
        'item_name': 'certification',
        'label_field': 'name',
        'fields': [
            field('name', 'name', required=True),
            field('issuer', 'issuer', required=True),
            field('icon', 'icon', required=True, check=check_icon, help='e.g. fas fa-certificate'),
            field('url', 'verification link', check=check_link, help='optional'),
        ],
    },
    'about': {
        'title': 'About',
        'file': 'about',
        'fields': [
            field('paragraphs', 'about text', 'paragraphs', required=True,
                  help='leave a blank line between paragraphs; **bold** is allowed'),
        ],
    },
    'education': {
        'title': 'Education',
        'file': 'about',
        'key': 'education',
        'list': True,
        'item_name': 'qualification',
        'label_field': 'title',
        'fields': [
            field('title', 'qualification', required=True),
            field('org', 'institution', required=True),
            field('note', 'note', help='optional, e.g. Distinction'),
        ],
    },
}


@bp.context_processor
def homepage_sections():
    return {'homepage_sections': [(name, section['title']) for name, section in SECTIONS.items()]}


def squash(text):
    return ' '.join(text.split())


def to_display(spec, value):
    """A stored value as the text (or checkbox state) shown in its form input."""
    kind = spec['kind']
    if kind == 'bool':
        return bool(value)
    if value is None:
        return ''
    if kind == 'lines':
        return '\n'.join(value)
    if kind == 'tags':
        return ', '.join(value)
    if kind == 'paragraphs':
        return '\n\n'.join(value)
    return str(value)


def from_form(spec, raw):
    """Convert submitted text to the stored value. Returns (value, problem)."""
    kind = spec['kind']
    if kind == 'bool':
        return bool(raw), None
    raw = raw.replace('\r\n', '\n')[:MAX_FIELD_LENGTH]
    if kind == 'lines':
        return [squash(line) for line in raw.split('\n') if line.strip()], None
    if kind == 'tags':
        return [squash(tag) for tag in raw.split(',') if tag.strip()], None
    if kind == 'paragraphs':
        return [squash(part) for part in re.split(r'\n\s*\n', raw) if part.strip()], None
    if kind == 'int':
        raw = raw.strip()
        if raw and not raw.isdigit():
            return None, 'must be a whole number'
        return (int(raw) if raw else None), None
    return squash(raw), None


def parse_fields(section, prefix, base):
    """Read one set of fields from the submitted form.

    Returns (item, raw, problems): the value to store, built on top of
    `base` so keys the form doesn't know about survive; the raw input, for
    showing the form again; and a list of what is wrong with it.
    """
    item = dict(base)
    raw = {}
    problems = []
    for spec in section['fields']:
        name = spec['name']
        raw[name] = request.form.get(prefix + name, '')
        value, problem = from_form(spec, raw[name])
        if not problem and value in EMPTY and spec['required']:
            problem = 'is required'
        if not problem and value not in EMPTY and spec['check'] and spec['kind'] != 'bool':
            problem = spec['check'](value)
        if problem:
            problems.append(f"{spec['label']} {problem}")
        if spec['kind'] == 'bool':
            raw[name] = value
        # Empty optional fields are left out of the file altogether.
        if value in EMPTY:
            item.pop(name, None)
        else:
            item[name] = value
    if not problems and section.get('finish'):
        section['finish'](item, problems)
    return item, raw, problems


def read_file(section):
    return content.load_content(section['file'])


def read_section(section):
    data = read_file(section)
    return data[section['key']] if 'key' in section else data


def save_section(section, value):
    """Save a section's new value. Returns False if nothing had changed."""
    current = read_file(section)
    data = {**current, section['key']: value} if 'key' in section else value
    if data == current:
        return False

    # Build the homepage with the new content before saving, so content
    # that would break the public page never gets committed.
    context = {name: content.load_content(name) for name in content.CONTENT_SECTIONS}
    context[section['file']] = data
    try:
        render_template('index.html', latest_post=None, **context)
    except Exception as error:
        raise storage.StorageError(f'Not saved: the homepage could not be built with this content ({error}).')

    text = json.dumps(data, indent=2, ensure_ascii=False) + '\n'
    storage.save_file(f"content/{section['file']}.json", text.encode('utf-8'),
                      f"Update homepage {section['title'].lower()}")
    return True


def finish_save(name, section, value, render_again):
    try:
        changed = save_section(section, value)
    except storage.StorageError as error:
        return render_again([str(error)], 502)
    if changed:
        flash_saved(f"{section['title']} saved.")
    else:
        flash('Nothing was changed.')
    return redirect(url_for('admin.content_edit', name=name))


@bp.route('/content/<name>', methods=['GET', 'POST'])
@login_required
def content_edit(name):
    section = SECTIONS.get(name)
    if section is None:
        abort(404)
    stored = read_section(section)
    if section.get('list'):
        return edit_list(name, section, stored)
    return edit_single(name, section, stored)


def edit_single(name, section, stored):
    def render(values, errors, status=200):
        return render_template('admin/content_form.html', name=name, section=section,
                               values=values, errors=errors), status

    if request.method == 'GET':
        return render({spec['name']: to_display(spec, stored.get(spec['name'])) for spec in section['fields']}, [])

    item, raw, problems = parse_fields(section, 'f-', stored)
    if problems:
        return render(raw, [problem[0].upper() + problem[1:] + '.' for problem in problems], 400)
    return finish_save(name, section, item, lambda errors, status: render(raw, errors, status))


def blank_row(section, position):
    values = {spec['name']: to_display(spec, None) for spec in section['fields']}
    return {'values': values, 'position': position, 'delete': False, 'label': ''}


def edit_list(name, section, stored):
    label_field = section['label_field']

    def render(rows, new_row, errors, status=200):
        return render_template('admin/content_form.html', name=name, section=section, rows=rows,
                               new_row=new_row, errors=errors), status

    if request.method == 'GET':
        rows = [{
            'values': {spec['name']: to_display(spec, item.get(spec['name'])) for spec in section['fields']},
            'position': index + 1, 'delete': False, 'label': item.get(label_field, ''),
        } for index, item in enumerate(stored)]
        return render(rows, blank_row(section, len(stored) + 1), [])

    def position_of(prefix, default):
        value = request.form.get(prefix + '_position', '').strip()
        return int(value) if value.isdigit() else default

    errors = []
    # The form addresses entries by their place in the saved list, so it
    # can't be applied if the list has changed underneath it.
    if request.form.get('count') != str(len(stored)):
        errors.append('This content changed after you opened the page. Reload it and make your changes again.')

    rows = []
    kept = []
    for index, original in enumerate(stored):
        prefix = f'i{index}-'
        item, raw, problems = parse_fields(section, prefix, original)
        row = {'values': raw, 'position': position_of(prefix, index + 1),
               'delete': bool(request.form.get(prefix + '_delete')),
               'label': original.get(label_field, '')}
        rows.append(row)
        if row['delete']:
            continue
        errors.extend(f"{row['label'] or 'Entry ' + str(index + 1)}: {problem}." for problem in problems)
        kept.append((row['position'], index, item))

    item, raw, problems = parse_fields(section, 'new-', {})
    new_row = {'values': raw, 'position': position_of('new-', len(stored) + 1), 'delete': False, 'label': ''}
    # The new-entry form counts as used once any of its text boxes is filled in.
    if any(value for value in raw.values() if isinstance(value, str)):
        errors.extend(f"New {section['item_name']}: {problem}." for problem in problems)
        kept.append((new_row['position'], len(stored), item))

    if errors:
        return render(rows, new_row, errors, 400)
    value = [item for _, _, item in sorted(kept, key=lambda entry: entry[:2])]
    return finish_save(name, section, value, lambda errors, status: render(rows, new_row, errors, status))
