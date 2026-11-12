# auto-short

コード生成の Shorts 動画を自動で作り、YouTube に投稿するパイプライン。

## セットアップ

```
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
```

ffmpeg は `imageio-ffmpeg` 同梱のものを使うので、別途インストール不要。

## 使い方

```
.venv\Scripts\python -m autoshort make --seed 3              # out/ に mp4 と json を1本出力
.venv\Scripts\python -m autoshort batch --start-seed 10 --count 5
.venv\Scripts\python -m autoshort upload out\ring_escape_00003.mp4 --privacy private
```

メタデータ(タイトル、パラメータ、投稿 ID)は `history/` に保存してコミットする。
クラウド実行と手元実行で、使った seed と公開枠をここで共有する。

同じ seed からは同じ動画が出る。退屈な展開(長すぎる、リングが割れない時間が続く等)は
`autoshort/sim.py` の `quality_ok` が弾き、初期条件を変えて再試行する。

## YouTube セットアップ(初回のみ、手作業)

1. Google Cloud Console でプロジェクトを作り、YouTube Data API v3 を有効化する。
2. OAuth 同意画面を設定し、自分の Google アカウントをテストユーザーに追加する。
3. OAuth クライアント ID(種類: デスクトップアプリ)を作り、JSON を `secrets/client_secret.json` に置く。
4. 初回の `upload` 実行時にブラウザが開くので、投稿先チャンネルで許可する。

未監査の API プロジェクトからの投稿は非公開に固定される。公開で自動投稿するには
YouTube API の監査申請が必要。

## 毎日の自動投稿(GitHub Actions、PC 不要)

`.github/workflows/daily.yml` が毎日 12:00 UTC(21:00 JST)に1本生成し、次の空き枠
(通常 00:00 JST)に予約投稿して、`history/` をコミットする。
Actions タブの「daily」→「Run workflow」で手動実行もできる。

必要な設定は1つだけ: リポジトリの Settings → Secrets and variables → Actions に
`YT_TOKEN_JSON` という名前で `secrets/token.json` の中身を登録する。

PR では `ci.yml` が各フォーマットのサンプルを1本ずつ描画し、Artifacts に置く。
