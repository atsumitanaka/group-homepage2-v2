const newsData = [
  {
    title: "新年度のキックオフミーティングを開催しました",
    date: "2026-02-01",
    category: "イベント",
    content: "2026年度の事業計画と目標について、全社員で共有しました。今年度も一丸となって頑張りましょう！"
  },
  {
    title: "新メンバーが加入しました",
    date: "2026-01-20",
    category: "お知らせ",
    content: "営業部に田中太郎さん、開発部に鈴木花子さんが新しく加わりました。温かく迎えてください。"
  },
  {
    title: "オフィス移転のお知らせ",
    date: "2026-01-15",
    category: "重要",
    content: "3月より新オフィスへ移転いたします。新住所は東京都渋谷区○○1-2-3 ビル10Fとなります。"
  },
  {
    title: "年末年始休業のお知らせ",
    date: "2025-12-20",
    category: "お知らせ",
    content: "誠に勝手ながら、12月29日から1月3日まで年末年始休業とさせていただきます。"
  },
  {
    title: "社内研修プログラムを開始します",
    date: "2025-12-10",
    category: "教育",
    content: "スキルアップを目的とした社内研修プログラムを開始します。詳細は各部署のマネージャーにお問い合わせください。"
  }
];

function openModal(index) {
  const news = newsData[index];
  document.getElementById('modal-category').textContent = news.category;
  document.getElementById('modal-title').textContent = news.title;
  document.getElementById('modal-date').textContent = news.date;
  document.getElementById('modal-content').textContent = news.content;
  document.getElementById('modal').classList.remove('hidden');
  document.body.style.overflow = 'hidden';
}

function closeModal(event) {
  if (!event || event.target === event.currentTarget) {
    document.getElementById('modal').classList.add('hidden');
    document.body.style.overflow = '';
  }
}

document.addEventListener('keydown', function(event) {
  if (event.key === 'Escape') {
    closeModal();
  }
});
