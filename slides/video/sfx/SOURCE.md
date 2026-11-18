# 音效来源

下表 3 个来自 Kenney（kenney.nl）的免费音效包，许可是 CC0：可以商用，不用署名。
2026-11-18 从各包页面点 Download 下载，原文件是 ogg，这里只转成 48 kHz 单声道 wav，没有改音色和音量。

| 文件 | 用在哪 | 音效包 | 原文件 |
|---|---|---|---|
| pop.wav | 元素弹出 | Interface Sounds（https://kenney.nl/assets/interface-sounds） | drop_002.ogg |
| tick.wav | 一串元素依次亮起 | Interface Sounds | tick_002.ogg |
| thud.wav | 数字、字落定 | Impact Sounds（https://kenney.nl/assets/impact-sounds） | impactSoft_medium_001.ogg |

这几个包的页面都标着“License: Creative Commons CC0”，包里的 License.txt 也写着 CC0、署名不是必须的。

## 后来从网上候选里试听选定的（2026-11-18）

先让 agy（Gemini，能听音频）按风格初筛，再由用户试听挑选。都转成 48 kHz 单声道 wav；whoosh 另外削掉了 3.5 kHz 以上（ffmpeg lowpass=f=3500），原声太亮、压在女声齿音上。

| 文件 | 用在哪 | 来源 | 许可 | 进不进仓库 |
|---|---|---|---|---|
| whoosh_soft.wav | 线画出、东西飞过 | Freesound「Whoosh_1.wav」，lzmraul，https://freesound.org/people/lzmraul/sounds/389458/ | CC0 | 进 |
| counter.wav | 数字滚动 | Pixabay「spin」，victorabdo（在 Pixabay 音效里搜 spin） | Pixabay Content License：免费商用、不用署名，但不能单独转发原文件 | 不进（见 .gitignore） |
| impact.wav | 整幅画面震一下（6 处） | Pixabay「Cinematic Impact Boom 04」，Universfield，https://pixabay.com/sound-effects/film-special-effects-cinematic-impact-boom-04-326123/ | 同上 | 不进 |
| transition.wav | 换段 | Pixabay「Swoosh 015」，Universfield，https://pixabay.com/sound-effects/film-special-effects-swoosh-015-383769/ | 同上 | 不进 |

不进仓库的三个，换一台电脑要录片时，按上面的页面重新下载，转成 48 kHz 单声道 wav，放回这个文件夹。

撞击、上升音和闪光是把候选放进片子里两处“震一下”，让 agy 听带人声的片段比较后定的：撞击用 Boom 04（比原来 Kenney 的 impactSoft_heavy_000 更轻快），上升音一个都不加。闪光 agy 选了 FX_UX quick shimmer，但用户整片听过后不要，也不加。

2026-11-18 又让 agy 看完整片评“整体和谐”，按它的意见去掉了 pop2（音高偏高、偏卡通，和 pop 交替像乒乓），连打的滴答、重叠的数字滚动、配在次要辅助线上的嗖声也都删了，音效从 185 个减到一百个上下。
