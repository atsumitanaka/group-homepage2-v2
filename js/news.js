let newsData = [];

function detectLang() {
  return location.pathname.includes('-en.html') ? 'en' : 'ja';
}

function renderNews(data, lang) {
  const list = document.getElementById('news-list');
  if (!list) return;
  list.innerHTML = '';

  data.forEach(function (item, index) {
    const category = lang === 'en' ? (item.category_en || item.category) : item.category;
    const title = lang === 'en' ? (item.title_en || item.title) : item.title;
    const body = lang === 'en' ? (item.body_en || item.body) : item.body;

    const card = document.createElement('div');
    card.className = 'news-card fade-in-up';
    card.innerHTML =
      '<div class="news-header">' +
        '<span class="category">' + category + '</span>' +
        '<span class="date">' + item.date + '</span>' +
      '</div>' +
      '<h2>' + title + '</h2>' +
      '<p class="preview">' + body + '</p>';
    card.style.cursor = 'pointer';
    card.addEventListener('click', function () { openModal(index, lang); });
    list.appendChild(card);
    // fade-in-upのアニメーションを発火させる
    requestAnimationFrame(function () { card.classList.add('visible'); });
  });
}

function openModal(index, lang) {
  var item = newsData[index];
  if (!item) return;
  var category = lang === 'en' ? (item.category_en || item.category) : item.category;
  var title = lang === 'en' ? (item.title_en || item.title) : item.title;
  var body = lang === 'en' ? (item.body_en || item.body) : item.body;

  document.getElementById('modal-category').textContent = category;
  document.getElementById('modal-title').textContent = title;
  document.getElementById('modal-date').textContent = item.date;
  document.getElementById('modal-content').innerHTML = body;
  document.getElementById('modal').classList.remove('hidden');
  document.body.style.overflow = 'hidden';
}

function closeModal(event) {
  if (!event || event.target === event.currentTarget) {
    document.getElementById('modal').classList.add('hidden');
    document.body.style.overflow = '';
  }
}

document.addEventListener('keydown', function (event) {
  if (event.key === 'Escape') {
    closeModal();
  }
});

document.addEventListener('DOMContentLoaded', function () {
  var lang = detectLang();
  var basePath = location.pathname.substring(0, location.pathname.lastIndexOf('/') + 1);
  fetch(basePath + 'data/news.json')
    .then(function (res) {
      if (!res.ok) throw new Error('Failed to load news.json: ' + res.status);
      return res.json();
    })
    .then(function (data) {
      newsData = data;
      renderNews(data, lang);
    })
    .catch(function (err) {
      console.error(err);
      document.getElementById('news-list').innerHTML = '<p>ニュースの読み込みに失敗しました。</p>';
    });
});
