const {validPhotos, renderGalleries, loadGalleries, startPhotoPolling} = require('../public/assets/js/photos.js');

const photo = (school = 'uva', category = 'hanukkah_photos', character = 'a') => ({
    school, category, src: 'assets/photos/' + character.repeat(64) + '.jpg', alt: 'Synthetic photo'
});

beforeEach(() => {
    jest.useFakeTimers();
    document.body.innerHTML = '<div id="alumni_gatherings" data-points="1"><span>2</span></div>'
        + '<div id="hanukkah_photos" data-points="1"><span>3</span></div>';
});
afterEach(() => {
    renderGalleries([]);
    jest.useRealTimers();
});

test('only accepts local approved-manifest image paths, known schools and categories', () => {
    const good = photo();
    expect(validPhotos([good, good, null, {...good, school: 'other'},
        {...good, category: 'other'}, {...good, src: 'https://drive.google.com/file/d/123'},
        {...good, src: 'assets/photos/../private.jpg'}, {...good, alt: ''}])).toEqual([good]);
    expect(validPhotos({photos: [good]})).toEqual([]);
});

test('associates photos with each school and category without changing score markup', () => {
    renderGalleries([photo(), photo('vt'), photo('uva', 'alumni_gatherings'), photo('vt', 'alumni_gatherings')]);
    const scores = document.querySelectorAll('[data-points]');
    expect(scores).toHaveLength(2);
    expect(scores[0].innerHTML).toBe('<span>2</span>');
    expect(scores[1].innerHTML).toBe('<span>3</span>');
    for (const score of scores) {
        expect(score.nextElementSibling.querySelector('.photo-gallery-uva')).not.toBeNull();
        expect(score.nextElementSibling.querySelector('.photo-gallery-vt')).not.toBeNull();
    }
    renderGalleries([]);
    expect(document.querySelectorAll('.photo-gallery-row')).toHaveLength(0);
});

test('manual navigation wraps, updates image and pauses rotation', () => {
    renderGalleries([photo(), photo('uva', 'hanukkah_photos', 'b')]);
    const gallery = document.querySelector('.photo-gallery');
    const image = gallery.querySelector('img');
    gallery.querySelector('[aria-label="Previous photo"]').click();
    expect(image.getAttribute('src')).toBe(photo('uva', 'hanukkah_photos', 'b').src);
    expect(gallery.querySelector('.photo-count').textContent).toBe('2 / 2');
    jest.advanceTimersByTime(12000);
    expect(gallery.querySelector('.photo-count').textContent).toBe('2 / 2');
    gallery.dispatchEvent(new KeyboardEvent('keydown', {key: 'ArrowRight', bubbles: true}));
    expect(gallery.querySelector('.photo-count').textContent).toBe('1 / 2');
});

test('broken image shows fallback and disables enlargement', () => {
    renderGalleries([photo('vt')]);
    const gallery = document.querySelector('.photo-gallery');
    gallery.querySelector('img').dispatchEvent(new Event('error'));
    expect(gallery.querySelector('.photo-fallback').hidden).toBe(false);
    expect(gallery.querySelector('.photo-frame').disabled).toBe(true);
    expect(gallery.querySelector('[aria-label="Next photo"]').hidden).toBe(true);
});

test('manifest fetch failures never throw or modify the scoreboard', async () => {
    await loadGalleries(jest.fn().mockRejectedValue(new Error('offline')));
    await loadGalleries(jest.fn().mockResolvedValue({ok: false}));
    expect(document.querySelectorAll('.photo-gallery')).toHaveLength(0);
    await loadGalleries(jest.fn().mockResolvedValue({ok: true, json: async () => [photo()]}));
    expect(document.querySelectorAll('.photo-gallery')).toHaveLength(1);
});

test('rotation pauses on hover and focus, resumes only after both clear, and respects the pause button', () => {
    renderGalleries([photo(), photo('uva', 'hanukkah_photos', 'b')]);
    const gallery = document.querySelector('.photo-gallery');
    const count = gallery.querySelector('.photo-count');
    const next = gallery.querySelector('[aria-label="Next photo"]');
    const toggle = gallery.querySelector('[aria-label="Pause automatic rotation"]');
    jest.advanceTimersByTime(6000);
    expect(count.textContent).toBe('2 / 2');
    gallery.dispatchEvent(new MouseEvent('mouseenter'));
    next.dispatchEvent(new FocusEvent('focusin', {bubbles: true}));
    next.dispatchEvent(new FocusEvent('focusout', {bubbles: true, relatedTarget: toggle}));
    gallery.dispatchEvent(new MouseEvent('mouseleave'));
    jest.advanceTimersByTime(12000);
    expect(count.textContent).toBe('2 / 2');
    gallery.dispatchEvent(new MouseEvent('mouseenter'));
    toggle.dispatchEvent(new FocusEvent('focusout', {bubbles: true}));
    jest.advanceTimersByTime(12000);
    expect(count.textContent).toBe('2 / 2');
    gallery.dispatchEvent(new MouseEvent('mouseleave'));
    jest.advanceTimersByTime(6000);
    expect(count.textContent).toBe('1 / 2');
    toggle.click();
    jest.advanceTimersByTime(6000);
    expect(count.textContent).toBe('1 / 2');
    expect(toggle.textContent).toBe('Play');
    toggle.click();
    jest.advanceTimersByTime(6000);
    expect(count.textContent).toBe('2 / 2');
    next.click();
    expect(count.textContent).toBe('1 / 2');
});

test('reduced motion starts paused but allows deliberate playback', () => {
    const previousMatchMedia = window.matchMedia;
    window.matchMedia = jest.fn().mockReturnValue({matches: true});
    try {
        renderGalleries([photo(), photo('uva', 'hanukkah_photos', 'b')]);
        const gallery = document.querySelector('.photo-gallery');
        const count = gallery.querySelector('.photo-count');
        jest.advanceTimersByTime(12000);
        expect(count.textContent).toBe('1 / 2');
        gallery.querySelector('[aria-label="Start automatic rotation"]').click();
        jest.advanceTimersByTime(6000);
        expect(count.textContent).toBe('2 / 2');
    } finally {
        if (previousMatchMedia === undefined) delete window.matchMedia;
        else window.matchMedia = previousMatchMedia;
    }
});

test('enlargement uses the selected local image and removes the dialog on close', () => {
    const prototype = Object.getPrototypeOf(document.createElement('dialog'));
    const originalShow = Object.getOwnPropertyDescriptor(prototype, 'showModal');
    const originalClose = Object.getOwnPropertyDescriptor(prototype, 'close');
    Object.defineProperty(prototype, 'showModal', {configurable: true, value: function () {
        this.setAttribute('open', '');
    }});
    Object.defineProperty(prototype, 'close', {configurable: true, value: function () {
        this.removeAttribute('open');
        this.dispatchEvent(new Event('close'));
    }});
    try {
        renderGalleries([photo()]);
        document.querySelector('[aria-label="Enlarge photo"]').click();
        const dialog = document.querySelector('dialog[open]');
        expect(dialog.querySelector('img').getAttribute('src')).toBe(photo().src);
        expect(dialog.querySelector('img').alt).toBe(photo().alt);
        dialog.querySelector('button').click();
        expect(document.querySelector('dialog')).toBeNull();
    } finally {
        if (originalShow) Object.defineProperty(prototype, 'showModal', originalShow);
        else delete prototype.showModal;
        if (originalClose) Object.defineProperty(prototype, 'close', originalClose);
        else delete prototype.close;
    }
});

test('single-photo galleries ignore navigation keys and missing score rows', () => {
    document.getElementById('alumni_gatherings').remove();
    renderGalleries([photo(), photo('vt', 'alumni_gatherings')]);
    const gallery = document.querySelector('.photo-gallery');
    gallery.dispatchEvent(new KeyboardEvent('keydown', {key: 'ArrowLeft', bubbles: true}));
    expect(gallery.querySelector('.photo-count').textContent).toBe('1 / 1');
    expect(document.querySelectorAll('.photo-gallery')).toHaveLength(1);
});

test('polling preserves the current carousel when the manifest is unchanged and removes revoked images', async () => {
    const photos = [photo(), photo('uva', 'hanukkah_photos', 'b')];
    const fetcher = jest.fn().mockResolvedValue({ok: true, json: async () => photos});
    await loadGalleries(fetcher);
    const gallery = document.querySelector('.photo-gallery');
    gallery.querySelector('[aria-label="Next photo"]').click();
    await loadGalleries(fetcher);
    expect(document.querySelector('.photo-gallery')).toBe(gallery);
    expect(gallery.querySelector('.photo-count').textContent).toBe('2 / 2');
    fetcher.mockResolvedValue({ok: true, json: async () => []});
    for (let poll = 0; poll < 4; poll++) {
        await loadGalleries(fetcher);
        expect(document.querySelector('.photo-gallery')).toBe(gallery);
    }
    await loadGalleries(fetcher);
    expect(document.querySelector('.photo-gallery')).toBeNull();
    expect(fetcher).toHaveBeenCalledWith('assets/photos/photos.json', {cache: 'no-store'});
});

test('a pending manifest request prevents overlapping polling', async () => {
    let complete;
    const fetcher = jest.fn(() => new Promise(resolve => { complete = resolve; }));
    const pending = loadGalleries(fetcher);
    await loadGalleries(fetcher);
    expect(fetcher).toHaveBeenCalledTimes(1);
    complete({ok: true, json: async () => [photo('vt')]});
    await pending;
    expect(document.querySelector('.photo-gallery-vt')).not.toBeNull();
});

test('polling updates only the changed school gallery', async () => {
    const items = [photo(), photo('uva', 'hanukkah_photos', 'b'), photo('vt')];
    const fetcher = jest.fn().mockResolvedValue({ok: true, json: async () => items});
    await loadGalleries(fetcher);
    const uva = document.querySelector('.photo-gallery-uva');
    const vt = document.querySelector('.photo-gallery-vt');
    uva.querySelector('[aria-label="Next photo"]').click();
    items.push(photo('vt', 'hanukkah_photos', 'c'));
    await loadGalleries(fetcher);
    expect(document.querySelector('.photo-gallery-uva')).toBe(uva);
    expect(uva.querySelector('.photo-count').textContent).toBe('2 / 2');
    expect(document.querySelector('.photo-gallery-vt')).not.toBe(vt);
    fetcher.mockResolvedValue({ok: true, json: async () => ({invalid: true})});
    await loadGalleries(fetcher);
    expect(document.querySelector('.photo-gallery-uva')).toBe(uva);
});

test('polling starts immediately and refreshes every five seconds', async () => {
    const fetcher = jest.fn().mockResolvedValue({ok: true, json: async () => []});
    const interval = startPhotoPolling(fetcher);
    try {
        await jest.advanceTimersByTimeAsync(4999);
        expect(fetcher).toHaveBeenCalledTimes(1);
        await jest.advanceTimersByTimeAsync(1);
        expect(fetcher).toHaveBeenCalledTimes(2);
    } finally {
        clearInterval(interval);
    }
});


test('temporary empty manifests preserve the carousel and its position', async () => {
    const photos = [photo(), photo('uva', 'hanukkah_photos', 'b')];
    const fetcher = jest.fn().mockResolvedValue({ok: true, json: async () => photos});
    await loadGalleries(fetcher);
    const gallery = document.querySelector('.photo-gallery');
    gallery.querySelector('[aria-label="Next photo"]').click();
    fetcher.mockResolvedValue({ok: true, json: async () => []});
    for (let poll = 0; poll < 4; poll++) {
        await loadGalleries(fetcher);
        expect(document.querySelector('.photo-gallery')).toBe(gallery);
    }
    fetcher.mockResolvedValue({ok: true, json: async () => photos});
    await loadGalleries(fetcher);
    expect(document.querySelector('.photo-gallery')).toBe(gallery);
    expect(gallery.querySelector('.photo-count').textContent).toBe('2 / 2');
    // A subsequent empty response must begin a new confirmation sequence.
    fetcher.mockResolvedValue({ok: true, json: async () => []});
    await loadGalleries(fetcher);
    expect(document.querySelector('.photo-gallery')).toBe(gallery);
});

test.each([
    {ok: false},
    {ok: true, json: async () => ({invalid: true})},
    {ok: true, json: async () => { throw new Error('invalid JSON'); }},
])('an unsuccessful poll interrupts empty-manifest confirmation', async failure => {
    const fetcher = jest.fn().mockResolvedValue({ok: true, json: async () => [photo()]});
    await loadGalleries(fetcher);
    const gallery = document.querySelector('.photo-gallery');
    const empty = {ok: true, json: async () => []};
    fetcher.mockResolvedValue(empty);
    for (let poll = 0; poll < 4; poll++) await loadGalleries(fetcher);
    fetcher.mockResolvedValue(failure);
    await loadGalleries(fetcher);
    fetcher.mockResolvedValue(empty);
    for (let poll = 0; poll < 4; poll++) {
        await loadGalleries(fetcher);
        expect(document.querySelector('.photo-gallery')).toBe(gallery);
    }
    await loadGalleries(fetcher);
    expect(document.querySelector('.photo-gallery')).toBeNull();
});

test('removing one gallery while another remains is immediate', async () => {
    const fetcher = jest.fn().mockResolvedValue({ok: true, json: async () => [photo(), photo('vt')]});
    await loadGalleries(fetcher);
    const vt = document.querySelector('.photo-gallery-vt');
    fetcher.mockResolvedValue({ok: true, json: async () => [photo('vt')]});
    await loadGalleries(fetcher);
    expect(document.querySelector('.photo-gallery-uva')).toBeNull();
    expect(document.querySelector('.photo-gallery-vt')).toBe(vt);
});
