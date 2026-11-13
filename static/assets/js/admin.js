/* Post editor: live markdown preview. */
(function () {
	'use strict';

	var form = document.getElementById('post-form');
	if (!form) return;

	var body = document.getElementById('body');
	var preview = document.getElementById('preview');
	var token = form.querySelector('input[name="csrf_token"]').value;
	var timer = null;

	function refresh() {
		var data = new FormData();
		data.append('body', body.value);
		fetch(form.dataset.previewUrl, {
			method: 'POST',
			headers: { 'X-CSRFToken': token },
			body: data,
			credentials: 'same-origin'
		})
			.then(function (response) {
				// A redirect means the session ended; keep the last preview.
				if (!response.ok || response.redirected) return null;
				return response.text();
			})
			.then(function (html) {
				if (html !== null) preview.innerHTML = html;
			})
			.catch(function () {});
	}

	body.addEventListener('input', function () {
		clearTimeout(timer);
		timer = setTimeout(refresh, 400);
	});
})();
