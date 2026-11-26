const {validPhotos, renderGalleries, loadGalleries} = require('../public/assets/js/photos.js');

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
