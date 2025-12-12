# データモデリング（鳥瞰）

`データモデル.yml` を正として、主要関係線（鳥瞰用）のSVGを生成し `output.html` に埋め込みます。

## 鳥瞰の関係線を更新する

1. `データモデル.yml` の `birdseye.entities` / `birdseye.relations` を編集
   - `entities[].pos`（`x`,`y`）で線の接続点座標を調整できます。
   - L字にしたい場合は `relations[].via` に中継点を複数指定します（`{x:..., y:...}`）。
2. 生成スクリプトを実行

```bash
node tools/generate-relations.js
```

これにより `output.html` の `<!-- BEGIN AUTO-RELATIONS -->` ～ `<!-- END AUTO-RELATIONS -->` の範囲が再生成されます。

## 注意
- ブラウザ側のJSは使わず、生成時に静的HTMLへ焼き込む方式です。
