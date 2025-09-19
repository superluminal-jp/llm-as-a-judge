# 非開示情報評価基準テスト

このディレクトリには、作成した評価基準を CLI でテストするためのサンプル情報とツールが含まれています。

## ファイル構成

- `non_disclosure_test_batch.jsonl` - CLI バッチ処理用のテストサンプル
- `administrative_disclosure_criteria.json` - 評価基準の詳細定義
- `administrative_disclosure_prompt_template.txt` - プロンプトテンプレート
- `evaluation_test_sheet.md` - 手動評価用のテストシート
- `README.md` - このファイル

## テストサンプルの概要

### 1. 個人情報保護 (sample_001)

- **内容**: 特定個人の詳細な医療診断記録
- **期待スコア**: 1 (強く不開示)
- **理由**: 明確に特定個人を識別できる高度に機密性の高い医療情報

### 2. 法人情報保護 (sample_002)

- **内容**: 大手製造業の新製品開発に関する機密情報
- **期待スコア**: 1 (強く不開示)
- **理由**: 企業の競争上の地位に重大な影響を与える営業秘密

### 3. 国家安全保障 (sample_003)

- **内容**: 自衛隊の新装備導入に関する機密情報
- **期待スコア**: 1 (強く不開示)
- **理由**: 国の安全保障に直接関わる機密情報

### 4. 公共安全 (sample_004)

- **内容**: 進行中の重大事件の捜査情報
- **期待スコア**: 1 (強く不開示)
- **理由**: 進行中の捜査に重大な妨害を与える情報

### 5. 内部審議保護 (sample_005)

- **内容**: 重要政策の内部検討資料
- **期待スコア**: 2 (不開示の可能性)
- **理由**: 率直な意見交換を抑制する可能性がある

### 6. 行政運営保護 (sample_006)

- **内容**: 地方自治体の監査手順と結果
- **期待スコア**: 2 (不開示の可能性)
- **理由**: 監査の有効性を損なう可能性がある

### 7. 開示可能 (sample_007)

- **内容**: 公共政策の一般的な情報
- **期待スコア**: 5 (明確に開示)
- **理由**: いずれの不開示事由にも該当しない

### 8. 部分開示対象 (sample_008)

- **内容**: 開示可能部分と不開示部分が混在する情報
- **期待スコア**: 2 (不開示の可能性)
- **理由**: 法人情報保護の観点から不開示だが、部分開示により対応可能

## CLI でのテスト実行方法

### 1. バッチ処理での評価実行

```bash
# 基本的な実行
python -m llm_judge batch test_samples/non_disclosure_test_batch.jsonl

# 詳細オプション付き実行
python -m llm_judge batch test_samples/non_disclosure_test_batch.jsonl \
  --output test_results.json \
  --max-concurrent 3 \
  --batch-name "non_disclosure_evaluation_test"
```

### 2. プロンプトテンプレートを使用した実行

```bash
# プロンプトテンプレートを指定
python -m llm_judge batch test_samples/non_disclosure_test_batch.jsonl \
  --prompt-template test_samples/administrative_disclosure_prompt_template.txt \
  --output test_results.json
```

### 3. 設定ファイルを使用した実行

```bash
# 設定ファイルを指定
python -m llm_judge batch test_samples/non_disclosure_test_batch.jsonl \
  --config config.json \
  --output test_results.json
```

### 4. 手動評価（参考用）

1. `evaluation_test_sheet.md` を開く
2. 各サンプルについて、6 つの評価基準すべてに 1-5 のスコアを付与
3. 最終判定を行う

## 評価基準の使用方法

### スコアの意味

- **1**: 強く不開示 - 明確に不開示事由に該当
- **2**: 不開示の可能性 - おそらく不開示事由に該当
- **3**: 不明確 - 慎重な法的検討が必要
- **4**: 開示の可能性 - 適切な保護措置があれば開示可能
- **5**: 明確に開示 - 開示に問題なし

### 最終判定

各サンプルについて、6 つの基準すべてを評価し、**最も低いスコア**を最終判定とする。

## テスト結果の解釈

### 期待される結果

- 明確な不開示情報 (sample_001-004): スコア 1
- 不開示の可能性 (sample_005-006, 008): スコア 2
- 開示可能情報 (sample_007): スコア 5

### 評価基準の有効性確認

- **一貫性**: 同様の情報タイプについて一貫した評価結果
- **明確性**: 評価者が迷わずに判定できる
- **実用性**: 実際の行政実務で使用可能

## 注意事項

1. **法的検討**: 実際の情報公開判断では、必ず法的専門家の検討を経る
2. **文脈依存**: 情報の文脈や開示の目的によって評価が変わる場合がある
3. **継続的改善**: テスト結果に基づいて評価基準を継続的に改善する

## CLI 実行例

### 基本的な実行

```bash
# プロジェクトルートから実行
python -m llm_judge batch test_samples/non_disclosure_test_batch.jsonl
```

### 詳細オプション付き実行

```bash
python -m llm_judge batch test_samples/non_disclosure_test_batch.jsonl \
  --output results/non_disclosure_evaluation_results.json \
  --max-concurrent 2 \
  --batch-name "行政情報不開示事由評価テスト" \
  --prompt-template test_samples/administrative_disclosure_prompt_template.txt
```

### 結果の確認

```bash
# 結果ファイルの確認
cat results/non_disclosure_evaluation_results.json | jq '.'
```

## 期待される結果

CLI 実行により、各サンプルについて以下のような評価結果が得られます：

- **sample_001-004**: スコア 1（強く不開示）
- **sample_005-006**: スコア 2（不開示の可能性）
- **sample_007**: スコア 5（明確に開示）
- **sample_008**: スコア 2-3（部分開示の可能性）

## 今後の改善点

1. **部分開示の判断**: より詳細な部分開示の判断基準
2. **公益の考慮**: 公益上の理由による開示の判断基準
3. **時間的要因**: 情報の年代による評価の変化
4. **実務適用**: 実際の行政機関での試行運用
