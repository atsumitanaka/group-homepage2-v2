/**
 * Google Apps Script: ニュース投稿を受け取り、GitHubのnews.jsonを更新する
 *
 * === セットアップ手順 ===
 *
 * 1. https://script.google.com/ で新しいプロジェクトを作成
 * 2. このファイルの内容をコピーして貼り付け
 * 3. スクリプトプロパティに以下を設定（歯車アイコン → スクリプトプロパティ）:
 *    - GITHUB_TOKEN : GitHubのPersonal Access Token（repoスコープ）
 *    - GITHUB_REPO  : atsumitanaka/group-homepage2-v2
 * 4. デプロイ → 新しいデプロイ → ウェブアプリ
 *    - 実行するユーザー: 自分
 *    - アクセスできるユーザー: 全員
 * 5. 表示されたURLを admin/index.html の GAS_URL に設定
 */

function doPost(e) {
  try {
    var data = JSON.parse(e.postData.contents);
    var result = addNewsToGitHub(data);
    return ContentService.createTextOutput(JSON.stringify({ status: "ok", result: result }))
      .setMimeType(ContentService.MimeType.JSON);
  } catch (err) {
    return ContentService.createTextOutput(JSON.stringify({ status: "error", message: err.message }))
      .setMimeType(ContentService.MimeType.JSON);
  }
}

function addNewsToGitHub(newsItem) {
  var props = PropertiesService.getScriptProperties();
  var token = props.getProperty("GITHUB_TOKEN");
  var repo = props.getProperty("GITHUB_REPO");
  var path = "data/news.json";
  var branch = "main";

  // 1. 現在の news.json を取得
  var getUrl = "https://api.github.com/repos/" + repo + "/contents/" + path + "?ref=" + branch;
  var getResp = UrlFetchApp.fetch(getUrl, {
    headers: {
      Authorization: "Bearer " + token,
      Accept: "application/vnd.github.v3+json"
    }
  });
  var fileInfo = JSON.parse(getResp.getContentText());
  var currentContent = Utilities.newBlob(Utilities.base64Decode(fileInfo.content)).getDataAsString();
  var newsList = JSON.parse(currentContent);

  // 2. 新しいニュースを追加
  var entry = {
    date: newsItem.date || "",
    category: newsItem.category || "",
    category_en: newsItem.category_en || "",
    title: newsItem.title || "",
    title_en: newsItem.title_en || "",
    body: (newsItem.body || "").replace(/\n/g, "<br>"),
    body_en: (newsItem.body_en || "").replace(/\n/g, "<br>")
  };
  newsList.unshift(entry);

  // 日付降順ソート
  newsList.sort(function (a, b) {
    return (b.date || "").localeCompare(a.date || "");
  });

  // 3. コミット
  var newContent = JSON.stringify(newsList, null, 2) + "\n";
  var encoded = Utilities.base64Encode(Utilities.newBlob(newContent).getBytes());

  var putUrl = "https://api.github.com/repos/" + repo + "/contents/" + path;
  var putResp = UrlFetchApp.fetch(putUrl, {
    method: "put",
    headers: {
      Authorization: "Bearer " + token,
      Accept: "application/vnd.github.v3+json"
    },
    contentType: "application/json",
    payload: JSON.stringify({
      message: "ニュースを追加: " + (newsItem.title || "no title"),
      content: encoded,
      sha: fileInfo.sha,
      branch: branch
    })
  });

  return JSON.parse(putResp.getContentText()).commit.sha;
}
