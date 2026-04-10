# 開発ガイド

## 前提

- Python **3.12**（Lambda ランタイムと揃える）
- 本リポジトリは **AWS Lambda 上での実行**を主目的とする。ローカルから実 API を叩く CLI は含めない（テストはモック）。

## 依存関係

```bash
pip install -r requirements.txt -r requirements-dev.txt
```

- **ランタイム**: `requirements.txt`（Lambda バンドルにも使用）
- **開発**: `requirements-dev.txt`（pytest、pytest-cov、moto 等）

## テスト

```bash
pytest                                    # 全件
pytest tests/test_handler.py -v          # ハンドラのみ
pytest --cov=src --cov-report=term-missing # カバレッジ
```

- 外部 HTTP / AWS への実呼び出しは行わない（`unittest.mock` と `moto` で S3 をモック）。
- テスト数・カバレッジの目安はリポジトリ直下 [README.md](../README.md) の「テスト」節を参照。

## ディレクトリの読み方

| パス | 説明 |
|------|------|
| `src/` | Lambda にデプロイされるアプリケーションコード |
| `tests/` | `src` に対応したユニット／結合に近いテスト |
| `cdk/` | AWS CDK スタック（インフラ定義のみ） |
| `config/` | デプロイ用パラメータ JSON（シークレットは置かない） |
| `criteria/` | クライテリア定義のサンプル・本番用 JSON（実行時は S3 経由） |
| `contracts/` | JSON Schema（Lambda イベント／レスポンス・クライテリアファイル） |
| `specs/` | （任意・Git 対象外）spec-kit 等の長文仕様。ローカルでのみ保持 |

詳細は [repository-layout.md](repository-layout.md) を参照。

## コーディングの注意

- 公開 API は型ヒントと既存のログ／例外パターンに合わせる。
- 新しい環境変数を追加する場合は `src/config.py` と README の表を更新する。

## Git に含めないもの（AI / エディタ用）

[`.gitignore`](../.gitignore) で次を除外している。各開発者のマシンにだけ置く。

- `.claude/` — Claude Code 等のコマンド・設定
- `.cursor/` — Cursor 用コマンド等
- `.specify/` — Specify / spec-kit 用スクリプト・テンプレート
- `.speckit/` — Speckit 用（存在する場合）
- `.agents/` / `.codex/` — エージェント／Codex 用キャッシュ等

ルートの **`CLAUDE.md`** を置いてもよいが [`.gitignore`](../.gitignore) で除外される（エージェント向けメモはローカルのみ）。
