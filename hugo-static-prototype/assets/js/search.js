/**
 * Client-side title/author filter for the static work list.
 *
 * LIMITATION NOTE: This is a JavaScript polyfill for what a search backend
 * would do server-side. It has three hard constraints:
 *
 *   1. ALL records must be in the DOM — filters only what is rendered.
 *      For 14,974 scifi works that means a very large HTML page.
 *
 *   2. Only matches title and author strings. No stemming, no relevance
 *      ranking, no field weighting, no phrase proximity.
 *
 *   3. Filtering a list of 15k nodes is slow in the browser. In testing,
 *      keypress latency becomes noticeable above ~5,000 items.
 */

(function () {
  const input = document.querySelector('[data-search-target="input"]');
  const list  = document.querySelector('[data-search-target="list"]');

  if (!input || !list) return;

  const cards = Array.from(list.querySelectorAll('[data-title]'));

  input.addEventListener('input', function () {
    const query = this.value.trim().toLowerCase();

    cards.forEach(function (card) {
      if (!query) {
        card.hidden = false;
        return;
      }
      const title  = card.dataset.title  || '';
      const author = card.dataset.author || '';
      card.hidden = !(title.includes(query) || author.includes(query));
    });
  });
})();
