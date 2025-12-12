# データモデリング（鳥瞰）

`データモデル.yml` を正として、主要関係線（鳥瞰用）のSVGを生成し `output.html` に埋め込みます。

## 前提（固定）
- レイアウトは固定キャンバス（A4横相当、`1360×900`）として扱います。`output.html` の `.canvas-wrapper` / `<svg viewBox>` がこのサイズ前提です。
- HTML/CSSのみで「箱の座標から矢印を自動追従」できないため、箱の位置は固定し、関係線は `birdseye.entities.pos` / `birdseye.relations.via` の座標で管理します。
- 鳥瞰は主要リレーションのみ（`birdseye.relations` に列挙した線だけ）を描画します。必要以上に線を増やさない運用にします。
- 線種は最大3種類に限定します（`kind: flow|ref|cross`）。`output.html` の `.rel-flow`（実線=主要フロー）、`.rel-ref`（点線=マスタ参照）、`.rel-cross`（太線=システム跨ぎ強調）に対応します。

## 鳥瞰の関係線を更新する

1. `データモデル.yml` の `birdseye.entities` / `birdseye.relations` を編集
   - `entities[].pos`（`x`,`y`）で線の接続点座標を調整できます。
   - L字にしたい場合は `relations[].via` に中継点を複数指定します（`{x:..., y:...}`）。
2. 生成スクリプトを実行

```bash
npm install
node tools/generate-relations.js
```

これにより `output.html` の `<!-- BEGIN AUTO-RELATIONS -->` ～ `<!-- END AUTO-RELATIONS -->` の範囲が再生成されます。

## 注意
- ブラウザ側のJSは使わず、生成時に静的HTMLへ焼き込む方式です。
