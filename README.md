# 知行 · 校园智能服务助手

**ZHIXING COPILOT** · 有依据地回答，有回执地办事，有反馈地学习。

> 发布版本：`V26.1108.1`（2026-11-08；应用 health 版本同步）  
> 定位：可解释、可追溯、可演示的校园服务 + 学生学习空间原型  
> 技术栈：Python 3.14 / FastAPI / Pydantic v2 / SQLite / 原生 HTML+CSS+JS  
> 当前测试：**76 项 pytest 全部通过**

---

## 0. 当前快照（2026-11-08）

这一节是给下一个会话/接手人看的，先读这里，再往下看历史。**当前实际状态以 8011 为准；8000 可能是旧进程。**

| 项目 | 当前状态 |
|---|---|
| 主服务 | FastAPI，当前工作预览 `127.0.0.1:8011`；`8000` 可能仍在跑早期进程 |
| 启动数据 | `CAMPUS_DATA_DIR=data_demo`，`CAMPUS_LEARNING_DIR=learning_data` |
| 演示基线 | 5 个会话 / 4 张工单 |
| 测试 | **76 项通过** |
| 学生名册 | 25 届计科院 361 条，360 个有效学号，1 条缺学号 |
| 办事问答 | 仍用 MockLLM + 12 篇制度 / 60 分块 |
| 办事流程 | 3 条 DSL：校园卡补办、网络报修、请假（两级审批） |
| 工具 | 10 个；网络报修/请假仍是 Mock 业务 |
| 人工坐席 | 待认领、认领、办结；审批队列；站内通知 |
| 学习视觉 | **无 mock**；学生自己的 API Key，测试通过才能用 |
| 当前模型 | `DeepSeek / deepseek-flash`；图片识别是推理型模型，默认上限 16384 tokens |
| 识别 token | 上传区齿轮可调 2048/4096/8192/16384/32768 或自定义；超时 15–600 秒可调；每次上传独立，不是累计 |
| 学习 Key 存储 | Windows DPAPI 密文 + SHA-256 指纹，接口只返回掩码；不能覆盖，只能删除重录 |
| 学习数据 | `learning_data/learning.db`：任务、错题、专注、课程、模型配置；另有图片目录 |
| 错题回收站 | 题目/错题本**两个独立回收站**，保留 7 天，可恢复/彻底删除 |
| 日历 | 课程表/待办双模式；周/月视图；学期开始、课程周次、单双周；颜色/高度等可配 |
| 专注 | 番茄循环：专注/短休/长休、暂停继续、跳过、轮次、自动下一段、提示音 |
| 任务 | 本地规则/模型两种拆解；口水词清洗；无标点长列表兜底；可编辑/删除/手动新建 |
| 登录页 | 不再展示演示账号、不再预填 admin、登录输入框无 placeholder |
| 真实校园接口 | 只有 HTTP 适配器契约，没有真实校方联调 |

**必须记住的边界：**

1. 办事问答仍是 MockLLM，不要宣称“全系统接了真实大模型”；
2. 学习识别/批改走真实模型，但没有 Key 会明确拒绝，不会返回假题；
3. `deepseek-flash` 是推理型模型；图片识别 token 不够时会返回空正文，当前默认 16384，可调；
4. 解析排版是本地轻量 Markdown/公式层，不是完整 KaTeX；矩阵/复杂对齐环境不支持；
5. 识别上限和超时保存在浏览器 localStorage，换设备/换浏览器回到 16384 tokens / 120 秒；
6. 现实习/审批/报修仍是 Mock，真实学校系统未接。

---

## 1. 项目是什么

传统校园助手通常只做两件事之一：

- 会聊天，但答案没有依据，也办不成事；
- 能跳转业务系统，但学生要自己找入口、自己填信息。

本项目把两条线放在同一个学生工作台里：

```text
办事空间
  对话工作台 / 我的工单 / 知识库 / 评测

学习空间
  专注 / 考试周 / 任务清单 / 错题本 / 日历与课程
```

办事侧强调四条工程约束：

1. **引用校验**：答案必须能落到制度原文；
2. **人工确认**：写操作前必须停一下；
3. **幂等**：重复提交不能重复生成工单；
4. **审计**：每个节点、工具调用、确认都留痕。

学习侧强调三件事：

1. **专注有记录**，不是只放一个倒计时；
2. **任务能拆解**，并和专注时长关联；
3. **错题能重做**，答案在提交前不下发，提交后 AI 批改。

品牌含义：

- **知**：答案有依据、可核验；
- **行**：事情能办成、有回执；
- 合起来是“知行合一”。

---

## 2. 演进历史

这一节是项目的“history”，避免下一个会话重复踩坑。

| 阶段 | 做了什么 | 结果/边界 |
|---|---|---|
| P0 初始原型 | 双 Agent 路由、12 篇制度、60 分块、25 条检索评测、校园卡补办 16 节点流程、JSON 审计 | 能跑通“问答 + 补卡” |
| P1 品牌与名册 | 澄思 → **知行**；导入 25 届计科院 361 条学生数据；SQLite 学生库；多学院/多届导入 | 真实学号可走补卡，手机号脱敏 |
| P2 登录与权限 | 学生/辅导员/审计员/管理员；HMAC Token；会话/工单/审计/学生库 RBAC；HTTP 校园接口适配器 | 65 项测试；真实接口未联调 |
| P3 评测扩展 | 300 条 silver 集（240 同义改写 + 60 越界）、20 条任务、引用/拒答/任务指标、CLI/报告/看板 | 76 项测试；hard-negative 3.89%、越界误答 1.67%，均达标 |
| P4 学习空间 | 专注计时、任务清单、日历/课程、错题本、多模型配置档案、DPAPI Key、DeepSeek Flash | 学习空间已可用；真实识别需学生自己的 Key |
| P5 考试周 | 考试倒计时、错题驱动复习计划、每日任务、与专注联动、自动重排 | 考试数据手动录入；计划最多先排 14 天 |
| P6 DSL + 网络报修 | 补卡流程从 Python 搬到 `workflows/*.json`；新增网络报修第二条流程；工单记录定义版本/快照 | 76 项测试；网络报修仍是 Mock 工具 |
| P7 人工坐席 + 通知 | 转人工队列、认领、办结；站内通知与未读角标；结果写回 | 76 项测试；没有外部推送 |
| P8 请假流程 | 辅导员审批；超过 3 天学院二级审批；LVE 回执；驳回；撤回；销假 | 76 项测试；审批/销假仍是 Mock 业务 |
| P9 学习增强 | 间隔重复；学习报告；Teach-back；课程资料库（Word/PDF/TXT/MD）；作业文字/截图提取 | 76 项测试；复述/提取依赖学生模型 |
| P10 权限/注入/审计链 | HTTP 权限回归；hard-negative 3.89%、越界误答 1.67%；注入拦截；审计哈希链 | 76 项测试；外部锚定/持续红队未做 |
| P11 交互/回收站/日历/专注 | 登录页去演示账号与 placeholder；任务口水词清洗、无标点兜底、模型开关、删除/新建；番茄循环；日历周/月与自定义样式；题目/错题本双回收站；设置齿轮 | 76 项测试；识别上限存浏览器 localStorage |
| P12 解析/OCR 收口 | 查看解析抽屉；Markdown + 轻量公式/化学式排版；识别 token 可调；修复 1400 token 导致 DeepSeek 返回空正文 | 76 项测试；非完整 KaTeX |
| 当前 | 三条 DSL + 坐席/通知 + 学习闭环 + 交互收口 | 下一步真实系统、完整排版、跨设备设置 |

### 本次会话（2026-11-07 至 11-08）具体变更

- 登录页：移除演示账号按钮、`admin` 自动填充、所有登录输入框 placeholder；登录保持空白。
- 任务：逗号/顿号/连接词/无标点长列表拆解；口水词清洗；本地规则/模型提炼开关；清单删除与手动新建。
- 专注：番茄循环、短休/长休、暂停/继续、跳过、轮次、自动下一段、提示音、任务绑定。
- 日历：课程表/待办双模式；周/月视图；学期开始日期；课程周次 `1-16` / `5,10-17`、单双周；显示周末/时间/网格/颜色/高度/圆角/透明度；设置存 localStorage。
- 错题：题目/错题本两个独立回收站，7 天；删除二次确认；查看解析抽屉；轻量公式/化学式排版。
- 识别：`max_tokens` 上传区可调（2048/4096/8192/16384/32768/自定义）；每次上传独立；修复推理 token 吃光导致空正文。
- UI：`details` 三角设置改为齿轮按钮；静态资源版本化避免旧缓存。

### 关键转折

- **从“聊天套壳”转向“可解释办事系统”**：引用、确认、幂等、审计是核心，不是装饰。
- **从“一个学生账号”转向“真实名册登录”**：学号 + 姓名 + 学号后六位。
- **从“管理员一个 Key”转向“每个学生自己的模型配置”**：多档案、只写一次、DPAPI。
- **从“mock 识别”转向“没有 Key 就拒绝”**：不再用假题掩盖真实模型缺口。

---

## 3. 功能清单

### 3.1 办事空间

| 功能 | 说明 |
|---|---|
| 制度问答 | 规章/教务/学工/图书馆；TF-IDF + BM25 + RRF；引用编号 |
| 低置信度处理 | 自动改写重搜；二次失败拒答并转人工 |
| 校园卡补办 | 参数抽取 → 学籍校验 → 挂失 → 欠费 → 预约 → 确认 → 提交 → 回执 |
| 网络报修 | 学号/校区/类型/描述 → 生成报修单 → 确认 → 提交 → RPR 回执 |
| 请假申请 | 学号/校区/天数/原因 → 辅导员审批 → 超过 3 天学院审批 → LVE 回执；审批前可撤回，通过后可销假 |
| 流程 DSL | `workflows/*.json` 声明节点/边/条件；新增流程不改引擎 |
| 人工确认 | 写操作前暂停，确认/取消 |
| 幂等 | 同一确认重复提交返回原回执，不重复建单 |
| 工单 | 状态、节点轨迹、回执、失败原因 |
| 人工坐席 | 转人工队列、认领、办结、会话上下文 |
| 站内通知 | 转人工/完成/人工办结提醒，未读角标 |
| 审计 | JSONL，节点/工具/确认/错误/登录；prev_hash + hash 链式校验 |
| 命令行 | `python cli.py` 完整对话、确认、历史、审计 |

### 3.2 学习空间

仅学生和管理员可见。

| 功能 | 说明 |
|---|---|
| 专注 | 番茄循环（专注/短休/长休）、暂停继续、跳过、轮次、自动下一段、提示音、任务绑定、今日番茄统计 |
| 考试周 | 考试倒计时；按错题数量生成每日复习任务；生成/重排；任务可直接进入专注 |
| 任务清单 | 本地规则/模型两种拆解；口水词清洗；逐条改；导入；删除；完成勾选；逾期自动高优先级 |
| 任务与专注联动 | 点任务播放键开始计时；结束后累加实际投入；完成状态回写 |
| 错题本 | 建库；图片/文字录题；整本删除进错题本回收站 |
| 识别 token | 上传区齿轮调 2048/4096/8192/16384/32768 或自定义；超时 15–600 秒可调；每次上传独立 |
| 题目回收站 | 单题软删除 7 天，可恢复/彻底删除；与错题本回收站分开 |
| 查看解析 | 独立抽屉；Markdown、分式、根号、上下标、常见希腊字母、`\ce{}` 化学式 |
| 练习 | 题图 + 题干 + 作答；提交后 AI 批改、步骤反馈、参考解析、知识点 |
| 间隔重复 | 答对后 3/7/14/30 天复习；答错次日；今日复习队列 |
| 学习报告 | 最近 7 天专注、任务、到期复习、知识点分布 |
| Teach-back | 用自己的话复述，模型检查概念/步骤，不只对答案 |
| 课程资料 | 按课程粘贴/上传 Word/PDF/TXT/MD，课程内 TF-IDF 检索 |
| 作业提取 | 粘贴作业通知或上传截图，模型提取标题/课程/截止日，确认后导入任务 |
| 日历 | 课程表 / 待办任务双模式；周/月视图；学期开始日期、课程周次、单双周、周末/时间/网格/颜色/高度可配 |
| 课程表 | 手动添加；粘贴文本导入；课程作业备注 |
| 模型配置 | 多档案；DeepSeek/Qwen/自定义预设；测试连接；测试通过才能设为当前 |
| Key 安全 | 只写一次；DPAPI 加密；掩码 + 指纹；删除后才能重录 |

### 3.3 管理与评测

| 功能 | 说明 |
|---|---|
| 学生库 | 按学院/届/专业/班级/状态筛选；分页；手机号脱敏 |
| 学生导入 | Excel/CSV；`(届, 学院, 学号)` upsert；批次记录 |
| 评测中心 | 25 条冒烟集 + 300 条 silver + 20 条任务 |
| 评测报告 | Recall/MRR/nDCG、引用/拒答、任务成功率、置信区间 |
| 系统状态 | 工具注册表、模型标识、数据目录、集成模式 |

---

## 4. 系统架构

### 4.1 分层

```text
前端（原生 HTML/CSS/JS）
  ├─ 登录 / 角色菜单 / 个人中心
  ├─ 办事：对话、工单、审计、知识、学生库、评测、系统
  └─ 学习：专注、考试周、任务、错题本、日历/课程、模型配置
        │
FastAPI 路由层
  ├─ auth / sessions / chat / workflow / knowledge
  ├─ students / evaluation / learning / health
        │
服务层
  ├─ Router + QAAgent + WorkflowAgent
  ├─ ChatService / WorkflowEngine / ToolRegistry
  ├─ StudentRegistry / LearningService
  └─ EvaluationRunner / LearningStore
        │
基础设施
  ├─ JSON 会话/工单/审计
  ├─ SQLite 学生库
  ├─ SQLite 学习库（任务/错题/专注/课程/模型配置）
  ├─ MockLLM / MockCampusService
  └─ HttpCampusService（契约，未联调）
```

### 4.2 办事问答链路

```text
用户问题
 → 意图路由
 → 混合检索（TF-IDF + BM25 + RRF）
 → 低置信度改写
 → 抽取式生成（MockLLM）
 → 引用校验（编号/数字/重合度）
 → 不合格重生成
 → 仍不合格拒答 + 转人工
```

### 4.3 办事流程链路

```text
我要补办校园卡
 → 参数抽取
 → 学籍校验
 → 挂失判断（必要时自动挂失）
 → 欠费判断
 → 预约时段
 → 人工确认
 → 提交工单（幂等键）
 → 回执
```

### 4.4 学习错题链路

```text
上传图片/文字
 → 本地去 EXIF、缩放、保存
 → 学生自己的视觉模型（DeepSeek Flash/Qwen 等）
 → 题目 JSON（题干/选项/答案/解析/知识点/bbox）
 → 答案入库，不随题目下发
 → 练习页只给题目
 → 学生提交
 → 同一模型批改（步骤级）
 → 返回反馈 + 参考解析
```

---

## 5. 数据与持久化

| 路径 | 内容 | 是否随演示重置 |
|---|---|---|
| `data/sessions/` | 会话 JSON | 是 |
| `data/workorders/` | 工单 JSON | 是 |
| `data/audit/` | 审计 JSONL | 是 |
| `data/mock_services.json` | Mock 校园业务状态 | 是 |
| `registry/students.db` | 学生名册、导入批次 | **否** |
| `registry/imports/` | 原始导入文件留档 | **否** |
| `learning_data/learning.db` | 任务、错题、专注、课程、模型配置 | **否** |
| `learning_data/learning/images/` | 错题图片 | **否** |
| `runtime_work/` | 测试/临时目录 | 临时 |

> `START_DEMO.bat` 只清 `data/`，不删 `registry/` 和 `learning_data/`。  
> 学习 Key 存在 `learning_data/learning.db` 的 DPAPI 密文中，不写明文文件。

环境变量可覆盖：

```env
CAMPUS_DATA_DIR=data
CAMPUS_STUDENT_REGISTRY_DIR=registry
CAMPUS_LEARNING_DIR=learning_data
```

---

## 6. 登录、权限与安全

### 6.1 工作人员本地测试账号

**登录页面不再展示、不再预填这些账号，也没有 placeholder。** 下面是后端本地测试种子，只用于开发和自动化测试：

| 角色 | 账号 | 密码 | 可见范围 |
|---|---|---|---|
| 管理员 | `admin` | `admin123` | 全部 |
| 辅导员 | `counselor` | `counselor123` | 本学院学生/会话/审计 |
| 审计员 | `auditor` | `auditor123` | 全量只读、脱敏、系统状态 |

生产必须删除演示种子，接统一身份认证。

### 6.2 学生登录

学生没有通用演示账号，必须用名册：

```text
学号：名册中的 10 位学号
姓名：与 registry/students.db 完全一致
密码：学号后六位
```

- 姓名用字必须一致；
- 密码初值不做单独哈希，登录时与学号后六位比对；
- 生产必须改 CAS/OAuth2 + 强制改密。

### 6.3 RBAC

| 资源 | 学生 | 辅导员 | 审计员 | 管理员 |
|---|---|---|---|---|
| 自己的会话 | ✓ | ✓ | ✓ | ✓ |
| 本学院会话 | — | ✓ | ✓ | ✓ |
| 全量会话 | — | — | ✓ | ✓ |
| 学生库 | 仅自己 | 本学院 | 全量脱敏 | 全量 |
| 工单/审计 | 自己的 | 本学院/共享 | 全量 | 全量 |
| 系统状态 | — | — | ✓ | ✓ |
| 学习空间 | ✓ | — | — | ✓ |

### 6.4 学习 API Key 的安全语义

- 每个学生独立配置，互不可见；
- 第一次保存后，接口只返回 `sk-****1234` 和 SHA-256 指纹；
- 没有“查看明文”接口；
- 不能覆盖，必须删除旧配置再新增；
- 数据库存 Windows DPAPI 密文，不存明文；
- 服务端只在调用模型的内存中解密；
- 这不是“服务器永远无法解密”：拥有服务器/Windows 账户权限的人理论上可解密；生产应换 KMS/HSM；
- 严格单向哈希不能用于调用模型，因此采用“接口不可读 + 加密存储”。

### 6.5 图片隐私

当前是 **B 混合模式**：

```text
原图只在校内服务器
 → 本地去 EXIF、缩放、保存
 → 预处理图/题图发送给云模型
```

- 不是“图片不出校”；
- 严格不出校需要 C 校内私有化模型；
- 详见 `docs/LEARNING_IMAGE_PRIVACY.md`。

### 6.6 路由

**不提供学生路由开关。**

```text
学生浏览器 → 知行后端（固定代理）→ DeepSeek/Qwen
```

原因：Key 不能下发浏览器；图片要本地预处理；后端要审计/限流/重试。  
CC Switch 的本地路由是给桌面 CLI 切换供应商用的，不是本项目的学生变量。

---

## 7. 快速开始

### 7.1 环境

- Windows（DPAPI 依赖 Windows；学习 Key 加密在非 Windows 会拒绝）
- Python 3.14（项目当前环境）
- 依赖见 `requirements.txt`

### 7.2 安装

```bash
python -m pip install -r requirements.txt
```

### 7.3 启动

```bash
# 当前统一使用 8011
python -m uvicorn app.main:app --host 127.0.0.1 --port 8011
```

打开：

- 工作台：`http://127.0.0.1:8011`
- API 文档：`http://127.0.0.1:8011/docs`
- 健康检查：`http://127.0.0.1:8011/api/v1/health`

> `START_DEMO.bat` / `OPEN_DEMO.bat` 固定使用 **8011**；8000 可能仍有旧进程，不要用 8000 判断当前代码。

### 7.4 恢复演示基线

```bash
# 清空 data/，重建 5 会话 / 4 工单
START_DEMO.bat
```

或手动：

```bash
python scripts/seed_demo.py
```

> `START_DEMO.bat` 会设置 `CAMPUS_BASE_URL=http://127.0.0.1:8011/api/v1`；`seed_demo.py` 默认也连 8011，可用环境变量覆盖。

### 7.5 演示顺序

```text
管理员登录
 → 对话：奖学金材料（引用）
 → 对话：我要补办校园卡（确认 → 回执）
 → 工单：查看状态/轨迹
 → 审计：查看节点/工具/确认
 → 学生库：筛选/搜索/脱敏
 → 评测：25 条冒烟 + 300 条 silver + 20 任务
 → 退出 → 学生登录 → 学习空间
```

---

## 8. 学习空间配置

### 8.1 入口

学生登录 → 左侧「学习空间」→ 右上角「模型设置」。

### 8.2 新建配置

```text
供应商预设：DeepSeek / Qwen-VL / 自定义
配置名称：例如“我的 DeepSeek 高数”
备注：例如“高数拍题、错题解析”
官网链接：预设自动填
模型：预设自动填
Base URL：预设自动填
API Key：必填，保存后不可读
```

### 8.3 DeepSeek 配置

```text
Base URL: https://api.deepseek.com
模型:     deepseek-flash
```

官方说明：

- [图像理解](https://api-docs.deepseek.com/zh-cn/guides/vision)
- [V4-Flash-Vision-Exp 公告](https://api-docs.deepseek.com/zh-cn/news/news260821/)

> 旧的 `deepseek-v4-flash-vision-exp` 已下线，用 `deepseek-flash`；不要填 `deepseek-v4.1-flash`。

`deepseek-flash` 是推理型模型：图片识别会先消耗 reasoning tokens。默认 `max_tokens=16384`，读取超时 120 秒；复杂图片仍返回空正文时，上传区齿轮可调到 32768。超时可在 15–600 秒之间自行设置。每次上传独立，不是累计额度。上传后显示按等待时间估算的进度条、阶段和已等待时间。

### 8.4 Qwen 配置

```text
Base URL: https://dashscope.aliyuncs.com/compatible-mode/v1
模型:     qwen-vl-max
```

### 8.5 启用的规则

1. 保存配置后状态为「待测试」；
2. 点「测试连接」，真实请求模型；
3. 测试成功状态变「已连通」；
4. 只有「已连通」才能「设为当前」；
5. 当前配置才用于拍题识别/批改；
6. 没有当前配置或未测试时，上传题目返回 400，不返回 mock。

### 8.6 删除/更换 Key

- 已保存的 Key 不能查看、不能覆盖；
- 删除整个配置后重新新增；
- 删除后 Key 不可恢复；
- 服务端只在调用时解密。

---

## 9. API 概览

### 9.1 认证

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/api/v1/auth/login` | 学生/工作人员登录 |
| GET | `/api/v1/auth/me` | 当前用户 |

### 9.2 办事

| 方法 | 路径 | 说明 |
|---|---|---|
| GET/POST | `/api/v1/sessions` | 会话 |
| POST | `/api/v1/chat/send` | 发送消息 |
| POST | `/api/v1/chat/confirm` | 确认/取消 |
| GET | `/api/v1/workorders` | 工单列表 |
| GET | `/api/v1/workorders/{id}` | 详情 |
| GET | `/api/v1/audit/recent` | 审计 |
| GET | `/api/v1/audit/verify` | 审计哈希链校验 |
| GET | `/api/v1/handoff/queue` | 人工坐席队列 |
| POST | `/api/v1/handoff/{id}/claim` | 认领 |
| POST | `/api/v1/handoff/{id}/resolve` | 办结 |
| GET | `/api/v1/approvals/queue` | 待审批队列 |
| POST | `/api/v1/approvals/{id}/approve` | 审批通过 |
| POST | `/api/v1/approvals/{id}/reject` | 审批驳回 |
| POST | `/api/v1/approvals/{id}/withdraw` | 学生撤回待审批请假 |
| POST | `/api/v1/approvals/{id}/return` | 返校销假 |
| GET | `/api/v1/notifications` | 站内通知 |
| POST | `/api/v1/notifications/read` | 标记已读 |
| GET | `/api/v1/knowledge/documents` | 知识库 |
| GET | `/api/v1/students` | 学生库 |
| POST | `/api/v1/evaluation/run` | 25 条冒烟 |
| POST | `/api/v1/evaluation/extended/run?suite=...` | 300/生成/任务 |

### 9.3 学习

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/v1/learning/overview` | 学习概览 |
| GET | `/api/v1/learning/exam-room` | 考试周作战室 |
| POST/DELETE | `/api/v1/learning/exams` | 新增/删除考试 |
| POST | `/api/v1/learning/exams/{id}/plan` | 生成/重排复习计划 |
| GET/POST | `/api/v1/learning/tasks` | 任务 |
| POST | `/api/v1/learning/tasks/parse` | 自然语言拆解；`use_model=true` 走学生模型 |
| PATCH/DELETE | `/api/v1/learning/tasks/{id}` | 更新/删除 |
| POST | `/api/v1/learning/focus/start` | 开始专注 |
| POST | `/api/v1/learning/focus/{id}/stop` | 结束专注；可传 `elapsed_seconds` 排除暂停时间 |
| GET/POST | `/api/v1/learning/libraries` | 错题本 |
| GET | `/api/v1/learning/libraries/trash` | 错题本回收站 |
| DELETE | `/api/v1/learning/libraries/{id}` | 错题本软删除 |
| POST | `/api/v1/learning/libraries/{id}/restore` | 恢复错题本 |
| DELETE | `/api/v1/learning/libraries/{id}/permanent` | 彻底删除错题本 |
| GET | `/api/v1/learning/questions/trash` | 题目回收站 |
| DELETE | `/api/v1/learning/questions/{id}` | 软删除到回收站 |
| POST | `/api/v1/learning/questions/{id}/restore` | 恢复 |
| DELETE | `/api/v1/learning/questions/{id}/permanent` | 彻底删除 |
| POST | `/api/v1/learning/questions` | 录题（需已测试 Key）；可带 `max_tokens` 和 `timeout_seconds` |
| GET | `/api/v1/learning/questions/{id}` | 练习题目（无答案） |
| GET | `/api/v1/learning/questions/{id}/solution` | 参考答案与解析 |
| POST | `/api/v1/learning/questions/{id}/attempts` | 提交批改 |
| GET | `/api/v1/learning/review` | 今日错题复习队列 |
| GET | `/api/v1/learning/report?days=7` | 学习报告 |
| POST | `/api/v1/learning/questions/{id}/teachback` | 复述检查 |
| GET/POST | `/api/v1/learning/courses/{id}/materials` | 课程资料 |
| GET | `/api/v1/learning/courses/{id}/materials/search?q=` | 课程内检索 |
| POST | `/api/v1/learning/courses/{id}/materials/upload` | Word/PDF/TXT/MD 上传解析 |
| POST | `/api/v1/learning/assignments/extract` | 从作业文字/截图提取 |
| GET | `/api/v1/learning/calendar` | 月历 |
| GET | `/api/v1/learning/calendar/week?start=` | 周历 |
| GET/PUT | `/api/v1/learning/calendar/settings` | 学期开始日期 |
| GET/POST | `/api/v1/learning/courses` | 课程 |
| POST | `/api/v1/learning/courses/import` | 文本导入课表 |
| GET/POST | `/api/v1/learning/model-profiles` | 模型配置 |
| PATCH/DELETE | `/api/v1/learning/model-profiles/{id}` | 元数据/删除 |
| POST | `/api/v1/learning/model-profiles/{id}/test` | 测试连接 |
| POST | `/api/v1/learning/model-profiles/{id}/activate` | 设为当前 |

---

## 10. 测试与评测

### 10.1 pytest

```bash
python -m pytest -q
```

当前：**76 passed**。

覆盖：

- 认证/Token/RBAC；
- 检索/问答/引用；
- 工作流/确认/幂等；
- 学生名册/导入；
- HTTP 校园适配器契约；
- 学习任务/错题隐藏答案/专注；
- 错题/错题本软删除、恢复、彻底删除；
- 学习报告、复习、课程资料、作业提取；
- 多模型配置与 Key 一次性语义；
- HTTP 权限越权、Prompt 注入、审计哈希链。

### 10.2 300 条 silver 评测

```bash
python scripts/build_eval_dataset.py
python scripts/evaluate.py --suite all --split test \
  --output reports/eval-final.json
```

当前结果（2026-11-08 复跑）：

| 指标 | 结果 |
|---|---|
| 检索 Recall@5 | 1.0000，95% CI [0.9791, 1.0000] |
| MRR@5 | 0.9935 |
| nDCG@5 | 0.9952 |
| Hard-negative FPR | **0.0389（达标）** |
| 越界误答率 | **0.0167（达标）** |
| 引用存在率 | 0.9667（MockLLM） |
| 拒答准确率 | **0.9833（达标）** |
| 任务成功率 | 20/20，95% CI [0.8389, 1.0000] |
| 平均轮次 | 2.85 |
| 重复提交新增工单 | 0 |

> 这是 **silver 集**，不是人工金标；生成质量仍是 MockLLM。

报告：`docs/EVALUATION_REPORT.md`、`reports/eval-final.json`、`reports/eval-retrieval-round7.json`、`reports/eval-generation-round7.json`。

---

## 11. 目录结构

```text
campus-agent-mvp/
├─ app/
│  ├─ api/                 # 路由
│  ├─ auth/                # 登录/Token/RBAC
│  ├─ agents/              # QA / Workflow / Router
│  ├─ learning/            # 学习空间 store/service/secrets
│  ├─ knowledge/           # 12 篇制度 + 分块
│  ├─ retrieval/           # TF-IDF + BM25 + RRF
│  ├─ workflow/            # DSL 加载器 + 节点状态机
│  ├─ tools/               # 10 个工具（补卡/报修/请假）
│  ├─ notifications.py     # 站内通知
│  ├─ llm/                 # MockLLM 抽象
│  ├─ models/              # Pydantic
│  ├─ evaluation/          # 25 + 300 + 任务评测
│  ├─ student_registry.py  # 学生名册
│  ├─ config.py
│  ├─ deps.py
│  └─ main.py
├─ workflows/
│  ├─ card_reissue.json
│  ├─ network_repair.json
│  └─ leave.json
├─ static/
│  ├─ index.html
│  ├─ app.js
│  ├─ learning.js
│  ├─ handoff.js
│  ├─ style.css
│  └─ learning.css
├─ scripts/
│  ├─ seed_demo.py
│  ├─ import_students.py
│  ├─ build_eval_dataset.py
│  ├─ evaluate.py
│  └─ build_demo_*.py
├─ tests/                  # 76 项
├─ registry/               # 学生名册（持久）
├─ learning_data/          # 当前学习数据（持久；含错题图/Key 密文）
├─ learning_data_clean/    # 干净学习库（可选）
├─ data_demo/              # 当前办事演示数据
├─ data/                   # 可重置演示数据
├─ docs/
└─ reports/
```

---

## 12. 关键设计决策

### 12.1 为什么保留确定性工作流

补卡是强流程，不能让 Agent 自由发挥。节点状态机保证可测试、可审计、可恢复。

### 12.2 为什么引用校验不是“相似度”

相似度高不代表结论被支持。当前用编号、数字、重合度做工程约束；升级方向是 NLI/判官，但不把“相似”当“支持”。

### 12.3 为什么学生库独立于 `data/`

`data/` 是可重置演示数据；名册是真实持久数据。`START_DEMO` 删除 `data/` 不应删学生。

### 12.4 为什么学习数据独立

任务、错题、专注、模型配置属于学生长期数据，不能每次演示重置。

### 12.5 为什么 Key 不做纯哈希

纯哈希不可逆，无法用于调用模型。采用“接口不可读 + DPAPI 加密 + 删除重录”的折中；生产用 KMS/HSM。

### 12.6 为什么没有路由开关

后端本身就是固定代理；给学生开关会导致 Key 下发浏览器、绕过图片预处理和审计。

### 12.7 为什么学习空间没有 mock

mock 会让人误以为识别已跑通。没有 Key/未测试就明确 400，避免演示造假。

---

## 13. 当前限制 / 未完成

### 办事侧

- QA 仍是 MockLLM，不是真实大模型；
- HTTP 校园适配器只有契约测试，没有校方联调；
- 知识库只有 12 篇/60 分块；
- 评测 300 条是 silver，不是人工金标；
- hard-negative **3.89%**、越界误答 **1.67%**、拒答 **98.33%** 已达标，但这是 MockLLM/silver 条件下的结果；
- 学生密码是学号后六位，安全性弱，未做强制改密；
- 登录页不再展示演示账号，但后端仍保留本地测试种子。

### 学习侧

- 任务拆解默认仍是本地规则；打开「用模型提炼」才走学生模型；
- 无标点/口语长列表只能靠规则兜底，不能保证完全正确；
- 错题识别/批改依赖学生自己的 Key；DeepSeek 是推理型模型，图片识别默认 16384 tokens，可在上传区调高；
- 识别 token 上限存浏览器 localStorage，换设备回到 16384；
- 解析排版是本地轻量 Markdown/公式层，不是完整 KaTeX；矩阵/复杂对齐不支持；
- 解析表首选 **TeX Gyre Termes Math**，已内置 `static/fonts/texgyretermes-math.otf`；Latin Modern Math 作为后备；
- DeepSeek 是否返回 bbox 取决于模型；不返回就保留预处理整图；
- 图片 B 模式仍会把预处理图发给云模型，不是“图片不出校”；
- 提醒只是页面轮询，没有企业微信/短信；
- 课程表支持周次/单双周过滤，但没有整张课表图片识别，也没有课程编辑入口；
- 2026 节假日是示例，不是校历；
- 题目/错题本回收站保留 7 天，访问回收站时才清理过期数据；
- 模型配置元数据暂不支持页面编辑（可删除重建）。

### 环境

- **当前工作预览是 8011**；8000 可能还被早期进程占用，不能据此判断代码版本；
- 学习 Key 的 DPAPI 绑定 Windows 当前用户，换用户/换机无法解密；
- 非 Windows 环境会拒绝保存 Key。

---

## 14. 下一步 Roadmap

已完成：考试周、流程 DSL、网络报修、人工坐席/站内通知、请假两级审批/撤回/销假、学习增强、双回收站、日历周月视图、番茄专注、解析排版、识别 token 可调。  
下一步：真实系统联调、完整 KaTeX/字体、跨设备设置、评测金标。

优先级从高到低：

1. 真实校园系统只读联调（学生/一卡通/报修/审批），再开写操作沙箱；
2. 将轻量公式层替换/补全为离线 KaTeX + TeX Gyre Termes Math 字体，支持矩阵/对齐环境；
3. 识别 token 上限从浏览器 localStorage 迁到学生账号设置；
4. 课程编辑/删除与整张课表图片识别；
5. 任务提醒接企业微信/短信/邮件；
6. 真实 DeepSeek/Qwen 视觉题图批改回归；
7. 300 条 silver 人工抽检升级 gold；
8. 权限感知检索、Prompt 注入持续红队、审计链外部锚定；
9. 办事 QA 的 MockLLM 换真实模型（保持引用校验）。

---

## 15. 文档索引

| 文档 | 内容 |
|---|---|
| `docs/DEMO_GUIDE.pdf` | 17 页零基础演示脚本 |
| `docs/DEMO_MANUAL.pdf` | 36 页技术手册 |
| `docs/INTEGRATION.md` | 登录/RBAC/接口适配 |
| `docs/STUDENT_DATA.md` | 学生名册/导入/隐私 |
| `docs/WORKFLOW_DSL.md` | 流程 DSL/版本快照/网络报修/请假 |
| `docs/SECURITY.md` | 身份、Key、图片、审计与待补安全项 |
| `docs/QUALITY_GATES.md` | 测试/检索/安全门禁与当前红线 |
| `docs/EVALUATION_PLAN.md` | 评测扩展方案 |
| `docs/EVALUATION_REPORT.md` | 300 silver + 20 任务结果 |
| `docs/LEARNING_SPACE.md` | 学习空间/多配置/Key/回收站/识别 token/解析 |
| `docs/LEARNING_IMAGE_PRIVACY.md` | 图片本地化 vs 云端方案 |
| `docs/LEARNING_SPACE_PLAN.md` | 学习空间产品方案 |
| `CHANGELOG.md` | 版本记录与每次发布变更 |
| `VERSION` | 当前发布版本号 |

> `docs/DEMO_MANUAL.pdf` 与 `docs/DEMO_GUIDE.pdf` 是早期生成的演示文件；功能变更以 README + Markdown 文档为准。需要最新 PDF 时重新运行 `scripts/build_demo_manual.py` / `scripts/build_demo_guide.py`。

---

## 16. 给下一个会话的接手清单

1. 先读第 0 节“当前快照”、第 2 节“演进历史”和第 13 节“限制”；
2. 跑 `python -m pytest -q`，确认 **76 passed**；
3. 当前工作预览用 8011 + `CAMPUS_LEARNING_DIR=learning_data`；8000 可能是早期进程，不要把它当最新代码；
4. 用本地测试账号看办事/审批，用名册学生（学号 + 姓名 + 后六位）看学习空间；
5. 学习识别先在「模型设置」建配置并测试；DeepSeek 图片识别是推理型，token 不够会返回空正文，上传区可调 2048–32768；
6. 学习数据、错题图片、Key 密文都在 `learning_data/`，不要提交、不要重置；
7. 题目和错题本各有一个 7 天回收站，别把软删除当硬删除；
8. 解析渲染是本地轻量层，不是完整 KaTeX；改公式排版先看 `renderRichText`；
9. 不要声称“300 条是人工金标”或“全系统真实大模型”；
10. 改动后同步 README、测试数、`docs/LEARNING_SPACE.md` 与相关 Markdown；PDF 演示文件可能滞后。

---

## 17. 一句话总结

**办事侧证明“可解释、可追溯、能办成”；学习侧证明“能专注、能拆任务、能拍题重做”；两者共用一个有边界、有审计、有持久化的校园原型。**
