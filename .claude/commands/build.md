---
description: 仕様書をもとに、Codexに図のコードを作らせ、審査員が合格を出すまで自動で修正ループを回す
argument-hint: <図の名前（specs/ 内のファイル名、拡張子なし）>
---
# GANループ：`specs/$ARGUMENTS.md` の図を完成させる

あなたはディレクターです。CLAUDE.md のルールに従い、以下を進めてください。

## 0. 準備
- `specs/$ARGUMENTS.md` を読む。必須項目（目的・データ・図の種類・軸・出力形式）が欠けていれば、
  **ここで一度だけ** オーナーにまとめて質問する。揃っていれば質問せずに進む。
- `reports/$ARGUMENTS/` フォルダを作る。

## 1. 生成（Codex）
- ラウンド番号 N（1から開始）の指示書を `reports/$ARGUMENTS/round<N>_task.md` に書く。
  - 1回目：仕様書の要約と、作るべきスクリプト名・出力先
  - 2回目以降：前ラウンドの指摘を「致命的 → 重要 → 軽微」の順に統合した修正指示
- 次のコマンドでCodexに実装させる：
  ```
  codex exec --sandbox workspace-write --skip-git-repo-check "$(cat reports/$ARGUMENTS/round<N>_task.md)"
  ```
- Codexの返答を `reports/$ARGUMENTS/round<N>_codex.md` に保存する。

## 2. 判定（Claude側AI社員）
- まず `runner` に実行させる。失敗したら審査員は呼ばず、その結果を次ラウンドの修正指示にして1へ戻る。
- 成功したら `figure-reviewer` と `code-reviewer` を **並行して** 呼ぶ。
- 3人の結果を `reports/$ARGUMENTS/round<N>_review.md` に保存する。

## 3. 集計と判断
- 全員合格 → 4へ。
- 不合格 → N を1増やして1へ戻る。
- **N が5を超えたら止めて** 4へ（未完了として報告）。
- Codexがデータや仕様書を変更していたら、即座に元に戻させ、致命的違反として記録する。

## 4. オーナーへの最終報告
`reports/$ARGUMENTS/final.md` に以下をまとめ、チャットにも要点を表示する：
- 結果：完成 / 未完了
- 出力された図のファイルパス
- ラウンドごとの点数の推移（表）
- 主な修正内容（3〜5行）
- 残っている課題と、オーナーに判断してほしい点
