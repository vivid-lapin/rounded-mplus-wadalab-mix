# rounded-mplus-wadalab-mix

[自家製 Rounded M+](http://jikasei.me/font/rounded-mplus/about.html) と[和田研細丸ゴシック](https://sourceforge.net/projects/jis2004/)の合成フォントです。<br>
[TVCaptionMod2](https://github.com/xtne6f/TVCaptionMod2/blob/3d29b1e798d834d7dfc88ccb7707347497d785dc/TVCaptionMod2_Readme.txt)を参考に構成しています。

## 入力ファイル

- `rounded-mplus-1m-regular.ttf` ([自家製 Rounded M+](http://jikasei.me/font/rounded-mplus/about.html))
- `wlcmaru2004aribu.ttf` ([和田研細丸ゴシック](https://sourceforge.net/projects/jis2004/))
- `/System/Library/Fonts/ヒラギノ丸ゴ ProN W4.ttc` 収録範囲確認用

`rounded-mplus-1m-arib.ttf` は任意の参考フォントです。存在する場合は監査レポートに比較結果を追加しますが、生成処理には使いません。

## 実行コマンド

```sh
uv run python tools/font_audit.py
uv run python tools/build_composite_fonts.py
```

サンドボックス内では uv キャッシュへのアクセスが制限される場合があるため、必要に応じて `.venv` の Python を直接実行します。

```sh
.venv/bin/python tools/font_audit.py
.venv/bin/python tools/build_composite_fonts.py
```

`tools/build_composite_fonts.py` は生成フォントを `dist/` に、生成レポートを `analysis/build-report.md` に書き出します。

## 生成フォント

- `dist/rounded-mplus-1m-wadalab-mix.ttf`
  - フォント名: `Rounded M+ 1m WadaLab mix`
  - Rounded M+ を優先し、`wlcmaru2004aribu.ttf` のうち Rounded M+ に無いコードポイントをすべて補完します。
- `dist/rounded-mplus-1m-wadalab-comp-arib.ttf`
  - フォント名: `Rounded M+ 1m WadaLab comp ARIB`
  - Hiragino Maru Gothic ProN W4 に無いコードポイントだけを含みます。
  - 採用順は、Rounded M+、`wlcmaru2004aribu.ttf` 全体の順です。
  - ARIB STD-B24 と ARIB STD-B62 相当の文字集合だけを採用します。
  - JIS X 0208/JIS X 0201/JIS X 0213 と Latin-1 は Python の標準 codec と範囲指定から生成し、ARIB 追加文字と B24/B62 の PUA 再配置だけを `wlcmaru2004aribu.ttf` に実在するコードポイントから採用します。

生成フォントは横組み用のフォールバックフォントです。元フォント同士で互換のある縦書きメトリクス情報を揃えられないため、縦書きメトリクステーブルは省いています。

## ライセンスについて

### 自家製 Rounded M+

> 自家製 Rounded M+ は、M+ OUTLINE FONTS を、その自由なライセンス (M+ FONTS LICENSE) に基づき改変したもので、同一のライセンスによって提供されます。したがって、商用や再配布、ソフトウェアへの組み込み、改変などに関わらず、いかなる用途においても無償で自由に使用することができます。
> <http://jikasei.me/font/rounded-mplus/about.html>

### 和田研細丸ゴシック

> WadaLabMaruGo2004 is FreeFont (Open Font). Based on JIS X 0213:2004 (JIS2004) and including Japanese, Emojis, symbols and pictograms of Unicode 15.0. This font face is rounded. This license is public domain.
> <https://sourceforge.net/projects/jis2004/>

### rounded-mplus-wadalab-mix

パブリックドメイン (Unlicense)
