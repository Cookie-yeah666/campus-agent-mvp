# 错题本排版字体

错题本优先使用 **Latin Modern Math**，回退顺序为：

1. Latin Modern Math
2. TeX Gyre Termes Math
3. TeX Gyre Termes
4. Cambria Math / Times New Roman

## Latin Modern Math

已内置 `latinmodern-math.otf`，页面通过 `@font-face` 直接加载。

## 可选：TeX Gyre Termes Math

也可以把 `texgyretermes-math.otf` 放到本目录，作为备选。
字体来源：CTAN `fonts/tex-gyre`。

如果系统已经安装同名字体，浏览器会优先使用本机字体，不需要复制文件。
字体授权请以发行包内的 GUST Font License / 字体说明为准。
