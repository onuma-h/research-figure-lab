# 図の仕様書：sample_growth（動作確認用のサンプル）

## 1. 目的
- 3つの条件で、時間とともに測定値がどう変化するかを比較する。
- 使う場面：動作確認（仕組みが正しく回るかのテスト）

## 2. データ
- 入力ファイル：data/sample/growth.csv
- 使う列：time_h（時間）, condition（条件名）, replicate（反復番号）, value（測定値）
- 許可するデータ処理：条件・時間ごとに反復の平均と標準偏差を計算する

## 3. 図の内容
- 図の種類：折れ線（平均）＋エラーバー（標準偏差）
- パネル構成：1枚
- X軸：Time (h)、表示範囲 -1〜49（両端の点とエラーバーが枠で切れないための余白）、目盛りは 0, 12, 24, 36, 48
- Y軸：OD600、線形スケール、0から開始
- 凡例：条件名（Control, Treatment A, Treatment B）、図の内側の空いている場所
- ラベルの言語：英語

## 4. 体裁
- 出力形式：PNG と PDF の両方
- 解像度：300 dpi
- サイズ：幅 8.5cm × 高さ 6.5cm
- フォント：Arial（なければ DejaVu Sans）、8pt
- 配色：色覚多様性に配慮（Okabe-Ito 配色）、マーカーの形も条件ごとに変える

## 5. 出力
- スクリプト名：src/sample_growth.py
- 出力先：output/sample_growth/
- 出力ファイル名：sample_growth.png, sample_growth.pdf
