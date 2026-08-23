# 接入「行走」全身模型 —— Miara（推荐）

## 为什么
`mao_pro` 是**上半身/半身模型**，物理上没法「走路/移动」。要实现「站在地面 + 不断走动」，需要**全身 + 带行走动画**的模型。

**Miara** 是 Live2D 官方免费样例里明确带「**走路/walking** 全身动态动画」的模型：
- 全身模型，带行走等全身动画（官方示例用途：学习 Draw Order + 全身动画）
- SDK 兼容 Cubism 3.0 / 3.2，**兼容本项目的前端运行时**（pixi-live2d-display + CubismCore）
- 免费分发（Live2D Free Material License / Cubism Sample Data 条款）
  - 年销售额低于 1000 万日元的个人/小型企业可免费用于商业与非商业创作
  - 需同意 Free Material License 与 Sample Data 使用条款
  - 勿用于成人/暴力/易致反感或误解角色的表达

## 下载
前往 Live2D 官方样例页：
- https://www.live2d.com/en/learn/sample/miara/
- （或中文页 https://www.live2d.com/zh-CHS/download/sample-data/ 找「米亚拉/Miara」）
- 下载后得到一个 zip（约 38MB，含 `.cmo3` 源文件 + `runtime/` 运行时文件）

## 接入（插上即用，已适配）
1. 解压 Miara，找到里面的 **`runtime/` 文件夹**（含 `moc3`/`.model3.json`/`.motion3.json`/`.physics3.json`/`.cdi3.json`/纹理）。
2. 把整个 `runtime/` **复制到项目的 `live2d-models/miara/`**，即目录为：
   ```
   live2d-models/miara/runtime/model3.json        <- 关键：模型设置文件
   live2d-models/miara/runtime/miara.moc3
   live2d-models/miara/runtime/*.motion3.json
   ...
   ```
   （文件名是 `model3.json` 或 `miara.model3.json` 都行，`/live2d-models/info` 已兼容两种。）
3. 在 `model_dict.json` 的数组里**加一条**（保持 JSON 格式，注意逗号）：
   ```json
   {
     "name": "miara",
     "description": "全身行走模型（Miara，官方免费样例）",
     "url": "/live2d-models/miara/runtime/model3.json",
     "kScale": 0.5,
     "initialXshift": 0,
     "initialYshift": 0,
     "kXOffset": 1150,
     "idleMotionGroupName": "Idle",
     "pointerInteractive": true,
     "scrollToResize": true,
     "emotionMap": { "neutral": 0, "joy": 1, "anger": 2, "sadness": 3, "surprise": 4, "fear": 5, "shy": 6, "smile": 1 },
     "tapMotions": { "HitAreaHead": { "TapHead": 1 }, "HitAreaBody": { "TapBody": 1 } }
   }
   ```
   （`emotionMap`/`tapMotions` 里的动作组名须与 Miara 的 `model3.json` 里 `Motions`/`Expressions` 相符，可查看它里面实际的动作/表情再微调。）
4. 刷新浏览器 → 右上角**模型切换**选中 Miara → 角色即全身站在地面、并播放其 Idle/走动动画（配合本项目的滚动地面更生动）。

## 说明
- 也可不换 Mao Pro，直接用本项目已有的**全身 `shizuku`** 作为「站在地面」的角色（模型下拉里可切换）。
- Miara 让「走动」更真实（自带 walking 动画）。接入后无法再浏览器预览的部分，请你在浏览器里确认渲染效果。
- 若 `emotionMap`/`tapMotions` 与模型不一致，只会影响表情/点击动作，不影响加载。
