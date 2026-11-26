/* The manifest contains only published, approved images. Never read Forms from the browser. */
(() => {
    'use strict';

    const categories = ['alumni_gatherings', 'hanukkah_photos'];
    const schools = {uva: 'UVA', vt: 'Virginia Tech'};
    const imagePath = /^assets\/photos\/[a-f0-9]{64}\.jpg$/;

    function validPhotos(manifest) {
        if (!Array.isArray(manifest)) return [];
        const seen = new Set();
        return manifest.filter(photo => {
            if (!photo || !categories.includes(photo.category)
                || !Object.hasOwn(schools, photo.school)
                || typeof photo.src !== 'string' || !imagePath.test(photo.src)
                || typeof photo.alt !== 'string' || !photo.alt.trim()) return false;
            const key = [photo.category, photo.school, photo.src].join(':');
            if (seen.has(key)) return false;
            seen.add(key);
            return true;
        });
    }

    function element(tag, className, text) {
        const node = document.createElement(tag);
        if (className) node.className = className;
        if (text) node.textContent = text;
        return node;
    }

    function button(text, label) {
        const node = element('button', 'photo-control', text);
        node.type = 'button';
        node.setAttribute('aria-label', label);
        return node;
    }

    function openPhoto(photo, label) {
        const dialog = element('dialog', 'photo-dialog');
        dialog.setAttribute('aria-label', label);
        const close = button('Close', 'Close enlarged photo');
        const image = element('img', 'photo-enlarged');
        image.alt = photo.alt;
        image.src = photo.src;
        close.addEventListener('click', () => dialog.close());
        dialog.addEventListener('close', () => dialog.remove(), {once: true});
        dialog.append(close, image);
        document.body.append(dialog);
        dialog.showModal();
    }

    function createGallery(photos, school, category) {
        const label = schools[school] + ' ' + (category === 'hanukkah_photos'
            ? 'Hanukkah photos' : 'alumni and parent gatherings');
        const gallery = element('section', 'photo-gallery photo-gallery-' + school);
        gallery.setAttribute('aria-label', label);
        const heading = element('h3', 'photo-heading', schools[school]);
        const enlarge = button('', 'Enlarge photo');
        enlarge.classList.add('photo-frame');
        const image = element('img', 'photo-image');
        image.loading = 'lazy';
        const fallback = element('span', 'photo-fallback', 'Photo unavailable');
        fallback.hidden = true;
        enlarge.append(image, fallback);
        const controls = element('div', 'photo-controls');
        const previous = button('‹', 'Previous photo');
        const next = button('›', 'Next photo');
        const count = element('span', 'photo-count');
        count.setAttribute('aria-live', 'polite');
        const toggle = button('Pause', 'Pause automatic rotation');
        controls.append(previous, count, next, toggle);
        gallery.append(heading, enlarge, controls);

        let index = 0;
        let timer;
        const reducedMotion = typeof window.matchMedia === 'function'
            && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
        let paused = reducedMotion;
        function render() {
            const photo = photos[index];
            image.hidden = false;
            fallback.hidden = true;
            enlarge.disabled = false;
            image.alt = photo.alt;
            image.src = photo.src;
            count.textContent = (index + 1) + ' / ' + photos.length;
        }
        function move(amount) {
            index = (index + amount + photos.length) % photos.length;
            render();
        }
        function stop() {
            if (timer !== undefined) clearInterval(timer);
            timer = undefined;
        }
        function start() {
            if (!paused && photos.length > 1 && timer === undefined
                && !gallery.matches(':hover') && !gallery.contains(document.activeElement)) {
                timer = setInterval(() => move(1), 6000);
            }
        }
        function updateToggle() {
            toggle.textContent = paused ? 'Play' : 'Pause';
            toggle.setAttribute('aria-label', paused ? 'Start automatic rotation' : 'Pause automatic rotation');
        }
        function navigate(amount) {
            paused = true;
            stop();
            updateToggle();
            move(amount);
        }
        image.addEventListener('error', () => {
            image.hidden = true;
            fallback.hidden = false;
            enlarge.disabled = true;
        });
        enlarge.addEventListener('click', () => openPhoto(photos[index], label));
        previous.addEventListener('click', () => navigate(-1));
        next.addEventListener('click', () => navigate(1));
        toggle.addEventListener('click', () => {
            paused = !paused;
            updateToggle();
            if (paused) stop();
            else start();
        });
        gallery.addEventListener('mouseenter', stop);
        gallery.addEventListener('mouseleave', start);
        gallery.addEventListener('focusin', stop);
        gallery.addEventListener('focusout', event => {
            if (!gallery.contains(event.relatedTarget) && !paused && photos.length > 1 && timer === undefined) {
                timer = setInterval(() => move(1), 6000);
            }
        });
        gallery.addEventListener('keydown', event => {
            if (photos.length < 2) return;
            if (event.key === 'ArrowLeft' || event.key === 'ArrowRight') {
                event.preventDefault();
                navigate(event.key === 'ArrowLeft' ? -1 : 1);
            }
        });
        previous.hidden = next.hidden = toggle.hidden = photos.length === 1;
        updateToggle();
        render();
        start();
        return {gallery, stop};
    }

    let mounted = [];
    function renderGalleries(manifest) {
        mounted.forEach(({gallery, stop}) => { stop(); gallery.remove(); });
        mounted = [];
        document.querySelectorAll('.photo-gallery-row').forEach(row => row.remove());
        const photos = validPhotos(manifest);
        categories.forEach(category => {
            const score = document.getElementById(category);
            if (!score) return;
            const row = element('div', 'photo-gallery-row');
            Object.keys(schools).forEach(school => {
                const items = photos.filter(photo => photo.category === category && photo.school === school);
                if (!items.length) return;
                const instance = createGallery(items, school, category);
                mounted.push(instance);
                row.append(instance.gallery);
            });
            // Sibling, not child: scoring uses selectors inside data-points rows.
            if (row.childElementCount) score.after(row);
        });
    }

    async function loadGalleries(fetcher = fetch) {
        try {
            const response = await fetcher('assets/photos/photos.json', {cache: 'no-store'});
            if (!response.ok) return;
            renderGalleries(await response.json());
        } catch {
            // An unavailable gallery must never prevent the scoreboard loading.
        }
    }

    if (typeof module !== 'undefined') {
        module.exports = {validPhotos, renderGalleries, loadGalleries};
    } else {
        loadGalleries();
    }
})();
