# 学习空间方案：专注计时 + AI 错题本

> 目标：把学生端从“办事工具”扩展为“办事 + 学习”双空间。  
> 当前状态：第一版已实现；已移除学习空间的 mock 识别。每个学生在「模型设置」里配置自己的 API Key，服务端用 Windows DPAPI 加密；未配置 Key 时直接拒绝识别。

---

## 1. 产品结构

学生登录后，左侧顶部增加两个空间：

```text
办事空间
  对话工作台
  我的工单
  知识库
  评测中心

学习空间
  专注计时
  错题本
```

工作人员保持现有视图，不出现学习空间；管理员可在演示时查看。

### 1.1 办事空间

保留现有能力：

- 校园卡补办；
- 制度/教务/奖助/图书馆问答；
- 工单、回执、审计；
- 后续可扩报修、在读证明、请假等。

### 1.2 学习空间

第一版只做两个闭环：

1. **专注计时**：番茄钟 + 专注记录，不做“检测你是否碰手机”的虚假承诺；
2. **AI 错题本**：拍题/文字录入 → 提取题目 → 隐藏答案练习 → 提交批改 → 解析与错因。

“心流”建议作为产品文案里的**专注状态**，不要宣称医学/心理学意义上的心流诊断；可展示“本次专注 25 分钟、中断 1 次、累计 6 小时”。

---

## 2. AI 错题本闭环

### 2.1 学生视角

```text
新建错题本（如“高等数学上错题本”）
  → 拍照/上传题目图片，或直接粘贴文字
  → AI 提取：题干、选项、公式、题图、知识点
  → 学生可修改识别结果后保存
  → 进入练习：只显示题目和题图，不显示答案
  → 学生写解答/思路
  → 提交
  → AI 批改：结论对错 + 步骤问题 + 参考解析 + 知识点
  → 加入复习队列
```

关键约束：

- **答案不能随题目一起下发到前端**；学生提交前，接口只返回 sanitized 题目。
- 原图必须保留；AI 可返回题目区域 bbox，后端裁切出“题图”，避免把整张作业纸当题图。
- 识别结果允许学生手动修正，不能把 OCR 错误直接当成标准题。
- 批改要区分“答案对/错”和“思路是否完整”，不能只看最终答案。

### 2.2 数据模型

```text
learning_libraries
  id, owner_id, name, subject, created_at

learning_questions
  id, library_id, owner_id
  original_image_path, question_image_path
  question_text, options_json
  reference_answer, analysis, knowledge_points
  difficulty, source, status, created_at

learning_attempts
  id, question_id, owner_id
  answer_text, score, correctness
  feedback_json, created_at

focus_sessions
  id, owner_id, mode, planned_seconds
  started_at, ended_at, completed, interruptions
```

### 2.3 API 草案

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/learning/libraries` | 新建错题本 |
| GET | `/learning/libraries` | 我的错题本 |
| DELETE | `/learning/libraries/{id}` | 删除 |
| POST | `/learning/questions` | 图片 base64/文字录入，调用视觉模型 |
| GET | `/learning/questions?library_id=` | 题目列表（不含答案） |
| GET | `/learning/questions/{id}` | 练习用题目（不含答案） |
| GET | `/learning/questions/{id}/image` | 原图/题图，鉴权后返回 |
| POST | `/learning/questions/{id}/attempts` | 提交答案，返回批改与解析 |
| POST | `/learning/focus` | 记录一次专注 |
| GET | `/learning/focus/stats` | 专注统计 |

### 2.4 前端页面

- 学习首页：两个卡片，专注计时 + 错题本；
- 错题本列表：封面、题目数、最近练习；
- 错题本详情：题目卡片、掌握状态、开始练习；
- 录题弹窗：上传图片/粘贴文字、预览、识别中、可编辑结果；
- 练习页：题目图 + 题干 + 作答区 + 提交；
- 批改结果：对/错、步骤点评、参考解析、知识点、再练一次；
- 专注页：25/45/60 分钟、开始/暂停/结束、今日累计、最近记录。

---

## 3. 视觉模型怎么选

你的要求是：**图片理解 + 文字提取 + 公式/题图裁切 + 逻辑推理**。单一 OCR 不够，建议“多模态模型 + 可选 OCR 增强”。

### 3.1 推荐优先级

| 方案 | 适合 | 注意 |
|---|---|---|
| **Qwen2.5-VL / Qwen3-VL（阿里云百炼）** | 中文试卷、公式、表格、题图定位；支持 bbox | 首选，国内访问和中文场景更稳 |
| **Doubao-1.5-vision-pro（火山引擎）** | 中文文档、题目识别、拍题 | 也适合国内部署 |
| **GLM-4.5V（智谱）** | 中文图文理解、推理 | 适合作为备选 |
| **GPT-4o / Gemini 2.5** | 复杂推理、跨学科 | 成本和数据合规要评估 |

**建议首选 Qwen-VL 系列**，用 OpenAI 兼容接口接入；如果公式识别不稳，再叠 **Pix2Text/Mathpix** 做公式 OCR。

### 3.2 两阶段流水线

```text
图片
 → 预处理：旋转、缩放、去噪、透视矫正
 → 多模态模型：返回题目区域 bbox + 题干 + 选项 + 公式 + 图形说明
 → 后端裁切题图（Pillow/OpenCV）
 → 结构化 JSON 入库
 → 学生练习
 → 批改模型：按步骤 rubric 评分
```

### 3.3 识别结果 JSON

```json
{
  "question_text": "已知函数 f(x)=...，求...",
  "options": ["A. ...", "B. ..."],
  "question_bbox": [120, 340, 980, 760],
  "has_figure": true,
  "reference_answer": "...",
  "analysis": "第一步...第二步...",
  "knowledge_points": ["导数", "单调性"],
  "difficulty": "中等"
}
```

### 3.4 批改 JSON

```json
{
  "correctness": "partial",
  "score": 0.6,
  "step_feedback": [
    {"step": "求导", "status": "correct", "comment": "..."},
    {"step": "讨论单调性", "status": "missing", "comment": "..."}
  ],
  "final_feedback": "...",
  "reference_answer": "...",
  "knowledge_points": ["..."]
}
```

---

## 4. 真实模型接入方式

新增环境变量，不把密钥写进代码：

```env
CAMPUS_LEARNING_VISION_MODE=http
CAMPUS_LEARNING_VISION_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
CAMPUS_LEARNING_VISION_API_KEY=replace-me
CAMPUS_LEARNING_VISION_MODEL=qwen-vl-max
CAMPUS_LEARNING_JUDGE_MODEL=qwen-plus
```

没有配置时进入 **mock 模式**：

- 上传任意图片返回一道示例题；
- 批改按关键词/数值做简单判断；
- 页面必须显示“模拟识别，未接真实视觉模型”。

**不能把 mock 结果当真实 OCR 演示。** 这一点要在演示时讲清楚。

---

## 5. 分阶段实施

### Phase 1：可演示闭环（2–3 天）

- 学生端“办事 / 学习”切换；
- 专注计时（前端 localStorage + 后端记录可选）；
- 错题本 CRUD、图片上传、mock 识别；
- 练习隐藏答案、提交、mock 批改；
- 示例错题本 + 一道示例题。

### Phase 2：真实视觉模型（2–3 天）

- 接 Qwen-VL/豆包/GLM 的 OpenAI 兼容接口；
- 图片预处理、bbox 裁切、题图展示；
- 识别结果可编辑、失败重试；
- 真实批改 rubric；
- 图片访问鉴权、大小/格式限制、PII 清理。

### Phase 3：学习闭环（3–5 天）

- 错题复习队列、掌握度、间隔重复；
- 专注统计与学习报告；
- 导出错题本/打印；
- 知识点薄弱项分析；
- 老师/辅导员只读视图（可选）。

---

## 6. 需要先确认的三件事

1. **视觉模型供应商**：是否有阿里云百炼/火山/智谱/OpenAI 的 API Key？没有的话先做 mock 演示。
2. **学科范围**：第一版只做高等数学/大学物理，还是所有理科？公式 OCR 难度差别很大。
3. **图片隐私**：学生上传的作业照片是否允许离开校园网？如果不允许，需要本地 OCR + 本地模型，成本和效果都会变。

---

## 7. 我的建议

先做 **Phase 1**，把“学习空间 + 错题本 + 隐藏答案练习”跑通；同时把视觉模型做成适配器。  
没有 API Key 时用 mock 演示，有 Key 后只换适配器，不改前端和错题本数据模型。

模型首选：**Qwen-VL 系列**；公式识别不稳时再叠 **Pix2Text**。  
不要一上来做“全学科 + 自动切题 + 自动判卷”，先把一道高数题从拍照到批改跑通。
