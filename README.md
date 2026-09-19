# サロンメンバー サイト更新チェッカー 🚀

Googleスプレッドシートに登録されたサロンメンバーのWebサイト（ブログ等）を、毎朝6時（JST）にGitHub Actionsが自動巡回し、スマホでサクサク読める軽量ポータルサイト（GitHub Pages）として公開するシステムです。

---

## 📱 主な機能

- **完全無料・サーバー管理不要**: GitHub Actions と GitHub Pages だけで自動稼働
- **毎朝6:00自動更新**: 日本時間 朝6:00（UTC 21:00）に定期巡回して最新記事を抽出
- **スマホ最適化ポータル**:
  - 「24時間以内（NEW）」「3日以内」などの更新バッジ表示
  - 新着記事タイムライン & メンバー別表示のタブ切り替え
  - メンバー名・記事タイトルのリアルタイム検索
  - ダークモード自動対応
- **RSS自動検出**: WordPress、note、はてなブログなど、通常のトップURLからRSSフィードを自動判別
- **統合RSSフィード（`rss.xml`）**: 全メンバーの新着記事を束ねたRSSを配信。Feedly等のRSSリーダーでも1本で購読可能
- **手動更新対応**: GitHub上のボタンを1クリックするだけで、いつでも最新状態に更新可能

---

## 🛠️ セットアップ手順

### ステップ 1: Googleスプレッドシートの共有設定

1. 対象のスプレッドシート（「サイト_01」など）をブラウザで開きます。
2. 画面右上の **「共有」** ボタンをクリックします。
3. 一般的なアクセスの設定を **「リンクを知っている全員」** にし、役割を **「閲覧者」** に変更して「リンクをコピー」します。
   - コピーされたURL例: `https://docs.google.com/spreadsheets/d/1A2B3C4D.../edit?usp=sharing`

> **スプレッドシートの列の書き方**:
> 1行目にヘッダーとして **「名前」** と **「サイトURL」**（または「URL」）と書いておくだけで、自動で列を認識します。順序が逆でも問題ありません。

---

### ステップ 2: GitHubリポジトリの作成とプッシュ

本フォルダの内容をGitHubの新しいリポジトリにプッシュします。

```bash
git init
git add .
git commit -m "Initial commit: Salon Feed Checker"
git branch -M main
git remote add origin https://github.com/<あなたのユーザー名>/<リポジトリ名>.git
git push -u origin main
```

---

### ステップ 3: GitHub Pages の設定

リポジトリでGitHub Pagesを有効化します。

1. GitHubのリポジトリページを開き、**「Settings」** タブをクリックします。
2. 左メニューの **「Pages」** をクリックします。
3. **「Build and deployment」** の **「Source」** ドロップダウンで **「GitHub Actions」** を選択します。
   （※ これだけで、毎朝の更新時に自動デプロイされるようになります）

---

### ステップ 4: スプレッドシートURLをSecretに登録

スプレッドシートのURLをGitHubの環境変数に登録します。

1. リポジトリの **「Settings」** → 左メニューの **「Secrets and variables」** → **「Actions」** をクリックします。
2. **「New repository secret」** ボタンをクリックします。
3. 以下のように入力して保存します：
   - **Name**: `SPREADSHEET_URL`
   - **Secret**: ステップ1でコピーしたスプレッドシートのURL

---

### ステップ 5: 動作テスト（手動実行）

毎朝6時を待たずに、今すぐ初回のページを生成・公開できます。

1. リポジトリの **「Actions」** タブをクリックします。
2. 左側のワークフロー一覧から **「Daily Salon Site Update & Deploy」** を選択します。
3. 右側の **「Run workflow」** ドロップダウンをクリックし、緑色の **「Run workflow」** ボタンを押します。
4. 1分ほどで緑色のチェックマーク（完了）になり、GitHub PagesのURL（`https://<ユーザー名>.github.io/<リポジトリ名>/`）にアクセスするとポータルサイトが表示されます！

---

## 📲 スマホで快適に使う方法（アプリ化）

公開されたURLをスマホ（iPhone / Android）のブラウザで開き、**「ホーム画面に追加」** を行うと、専用アプリアイコンのようにワンタップで最新更新を確認できるようになります。

---

## 💻 ローカルでの開発・テスト

```bash
# 依存パッケージのインストール
pip install -r requirements.txt

# サンプルデータでHTMLをローカル生成（dist/index.html に出力されます）
python scripts/update_feeds.py --source data/members_sample.csv

# ブラウザでプレビュー
open dist/index.html
```
