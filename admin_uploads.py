"""Uploads: images for posts and projects, and the CV."""
import io
import os
import warnings

from flask import render_template, request, redirect, url_for, flash
from PIL import Image, ImageOps
from werkzeug.exceptions import RequestEntityTooLarge

import content
import storage
from admin import bp, login_required, flash_saved, slugify

MAX_UPLOAD_BYTES = 5 * 1024 * 1024
# Larger images are scaled down to fit; nothing on the site is shown wider.
MAX_IMAGE_SIDE = 2400
# Pillow format name -> file extension. Anything else is refused.
IMAGE_FORMATS = {'PNG': 'png', 'JPEG': 'jpg', 'WEBP': 'webp'}
IMAGE_FOLDERS = {'posts': 'Blog posts', 'projects': 'Projects'}
CV_PATH = 'static/assets/Bill_Benson_CV.pdf'

Image.MAX_IMAGE_PIXELS = 40_000_000


def clean_image(data):
    """Check an uploaded image and re-encode it.

    Returns (bytes, extension, (width, height)). Re-encoding from the pixels
    drops EXIF data (camera, GPS position) and anything else riding along in
    the file. Raises ValueError with a message for the user.
    """
    try:
        with warnings.catch_warnings():
            # An image big enough to trigger the bomb warning is refused.
            warnings.simplefilter('error', Image.DecompressionBombWarning)
            image = Image.open(io.BytesIO(data))
            image_format = image.format
            image.load()
    except Exception:
        raise ValueError('That file is not a usable image. Upload a PNG, JPEG or WebP.')
    if image_format not in IMAGE_FORMATS:
        raise ValueError('Only PNG, JPEG and WebP images can be uploaded.')

    # Apply the camera's rotation flag to the pixels before it is discarded.
    image = ImageOps.exif_transpose(image)
    if image_format == 'JPEG':
        image = image.convert('RGB')
    elif image.mode not in ('RGB', 'RGBA', 'L', 'LA'):
        image = image.convert('RGBA')
    image.thumbnail((MAX_IMAGE_SIDE, MAX_IMAGE_SIDE))
    image.info.clear()

    output = io.BytesIO()
    if image_format == 'PNG':
        image.save(output, 'PNG', optimize=True)
    else:
        image.save(output, image_format, quality=88)
    return output.getvalue(), IMAGE_FORMATS[image_format], image.size


def list_images():
    folders = []
    for folder, title in IMAGE_FOLDERS.items():
        directory = os.path.join(content.ROOT, 'static', 'images', folder)
        names = sorted(os.listdir(directory)) if os.path.isdir(directory) else []
        files = [f'{folder}/{name}' for name in names if name.rsplit('.', 1)[-1] in IMAGE_FORMATS.values()]
        folders.append((title, files))
    return folders


def image_details(path):
    """What the page shows for one image (path is '<folder>/<file>'), or None."""
    folder, _, name = path.partition('/')
    full_path = os.path.join(content.ROOT, 'static', 'images', folder, name)
    if folder not in IMAGE_FOLDERS or os.path.basename(name) != name or not os.path.isfile(full_path):
        return None
    with Image.open(full_path) as image:
        width, height = image.size
    return {'path': path, 'folder': folder, 'width': width, 'height': height}


def read_upload(field):
    """Return (filename, bytes) for an uploaded file, or raise ValueError."""
    try:
        upload = request.files.get(field)
    except RequestEntityTooLarge:
        upload = None
        too_large = True
    else:
        too_large = False
    data = upload.read(MAX_UPLOAD_BYTES + 1) if upload else b''
    if too_large or len(data) > MAX_UPLOAD_BYTES:
        raise ValueError(f'That file is too large. The limit is {MAX_UPLOAD_BYTES // (1024 * 1024)} MB.')
    if not data:
        raise ValueError('Choose a file to upload.')
    return upload.filename or '', data


@bp.route('/uploads')
@login_required
def uploads():
    shown = image_details(request.args.get('show', ''))
    return render_template('admin/uploads.html', folders=list_images(), image_folders=IMAGE_FOLDERS,
                           shown=shown, alt=request.args.get('alt', ''), cv_path=CV_PATH,
                           max_mb=MAX_UPLOAD_BYTES // (1024 * 1024))


@bp.route('/uploads/image', methods=['POST'])
@login_required
def upload_image():
    folder = request.form.get('folder', '')
    try:
        if folder not in IMAGE_FOLDERS:
            raise ValueError('Choose where the image is for.')
        filename, data = read_upload('file')
        name = slugify(request.form.get('name', '') or os.path.splitext(filename)[0])
        if not name:
            raise ValueError('Give the image a name using letters and numbers.')
        data, extension, _ = clean_image(data)
        path = f'static/images/{folder}/{name}.{extension}'
        if os.path.exists(os.path.join(content.ROOT, path)) and not request.form.get('replace'):
            raise ValueError(f'{name}.{extension} already exists. Pick another name, or tick "Replace".')
        storage.save_file(path, data, f'Upload image: {folder}/{name}.{extension}')
    except (ValueError, storage.StorageError) as error:
        flash(str(error), 'error')
        return redirect(url_for('admin.uploads'))
    flash_saved('Image uploaded.')
    alt = ' '.join(request.form.get('alt', '').split())[:300]
    return redirect(url_for('admin.uploads', show=f'{folder}/{name}.{extension}', alt=alt))


@bp.route('/uploads/cv', methods=['POST'])
@login_required
def upload_cv():
    try:
        _, data = read_upload('file')
        if not data.startswith(b'%PDF-'):
            raise ValueError('The CV must be a PDF file.')
        storage.save_file(CV_PATH, data, 'Update the hosted CV')
    except (ValueError, storage.StorageError) as error:
        flash(str(error), 'error')
        return redirect(url_for('admin.uploads'))
    flash_saved('CV replaced.')
    return redirect(url_for('admin.uploads'))
