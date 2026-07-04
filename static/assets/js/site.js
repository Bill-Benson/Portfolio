/* Site interactions: mobile nav, scroll-spy, reveal-on-scroll. No dependencies. */

(function () {
	'use strict';

	/* Mobile nav toggle */
	var toggle = document.querySelector('.nav-toggle');
	var links = document.querySelector('.nav-links');

	if (toggle && links) {
		toggle.addEventListener('click', function () {
			var open = links.classList.toggle('open');
			toggle.setAttribute('aria-expanded', open ? 'true' : 'false');
			toggle.querySelector('.fas').className = open ? 'fas fa-times' : 'fas fa-bars';
		});

		links.addEventListener('click', function (e) {
			if (e.target.closest('a')) {
				links.classList.remove('open');
				toggle.setAttribute('aria-expanded', 'false');
				toggle.querySelector('.fas').className = 'fas fa-bars';
			}
		});
	}

	/* Highlight the nav link for the section currently in view */
	var sections = document.querySelectorAll('main [id]');
	var navAnchors = document.querySelectorAll('.nav-links a[href^="#"]');

	if (sections.length && navAnchors.length && 'IntersectionObserver' in window) {
		var spy = new IntersectionObserver(function (entries) {
			entries.forEach(function (entry) {
				if (!entry.isIntersecting) return;
				navAnchors.forEach(function (a) {
					a.classList.toggle('active', a.getAttribute('href') === '#' + entry.target.id);
				});
			});
		}, { rootMargin: '-30% 0px -60% 0px' });

		sections.forEach(function (s) { spy.observe(s); });
	}

	/* Reveal-on-scroll */
	var revealables = document.querySelectorAll('[data-reveal]');
	var reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

	if (revealables.length && !reduced && 'IntersectionObserver' in window) {
		var revealer = new IntersectionObserver(function (entries) {
			entries.forEach(function (entry) {
				if (entry.isIntersecting) {
					entry.target.classList.add('revealed');
					revealer.unobserve(entry.target);
				}
			});
		}, { threshold: 0.12, rootMargin: '0px 0px -40px 0px' });

		revealables.forEach(function (el) { revealer.observe(el); });
	} else {
		revealables.forEach(function (el) { el.classList.add('revealed'); });
	}
})();
