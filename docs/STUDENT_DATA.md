# 学生库：多学院、多届导入说明

学生库与演示数据分开存放：

```text
registry/
├── students.db                 # SQLite 学生名册（持久化，START_DEMO 不会删除）
└── imports/
    └── students_2025_cs.xlsx   # 原始导入文件留档
```

`data/` 里是会话、工单、审计等演示数据；`START_DEMO.bat` 只清理 `data/`，不会动 `registry/`。

---

## 1. 当前已导入

| 项目 | 值 |
|---|---|
| 学院 | 计算机科学与技术学院 |
| 届别 | 2025 |
| 学生 | 361 条 |
| 有效学号 | 360 条 |
| 待补学号 | 1 条（原表学号为空） |
| 专业 | 计算机科学与技术、软件工程 |
| 班级 | 10 个 |
| 需关注 | 复读 3、未报到 1、保留资格 1、待补学号 1 |

数据来源：`最新班级表格.xlsx`，已复制为 `registry/imports/students_2025_cs.xlsx`。

---

## 2. 再导入其他学院 / 届

```bash
python scripts/import_students.py \
  --file path/to/students_2026_business.xlsx \
  --cohort 2026 \
  --college 商学院
```

先试运行、不写库：

```bash
python scripts/import_students.py \
  --file path/to/students_2026_business.xlsx \
  --cohort 2026 --college 商学院 --dry-run
```

覆盖导入（先清空该学院该届）：

```bash
python scripts/import_students.py \
  --file path/to/students_2026_business.xlsx \
  --cohort 2026 --college 商学院 --replace
```

支持 `.xlsx` / `.xlsm` / `.csv`；可用 `--sheet "Sheet1"` 指定工作表，`--db` 指定其他 SQLite 文件。

### 表头约定

支持中英文别名，顺序不限：

| 规范字段 | 常见表头 |
|---|---|
| 学号 | 学号、学生学号、student_id、id |
| 姓名 | 姓名、name |
| 专业 | 专业、major |
| 班级 | 班级名称、班级、class_name |
| 手机号 | 手机号码、手机号、电话、phone |
| 性别 | 性别、gender |
| 楼宇 / 房间 | 楼宇、宿舍楼 / 房间、宿舍房间 |
| 校区 | 校区、campus |
| 学院 / 届 | 学院 / 届、年级（也可用命令行参数覆盖） |

`学号`、`姓名`、`班级名称` 是必需的；学号不是 10 位数字时仍会入库，但标记为“待补学号”。

---

## 3. 数据模型

表 `students`：

| 字段 | 说明 |
|---|---|
| `record_key` | 主键：`届｜学院｜学号`；无学号时用行号+姓名+班级 |
| `student_id` | 10 位学号，可为空 |
| `cohort` | 届别，例如 `2025` |
| `college` | 学院 |
| `major` | 专业 |
| `class_name` | 班级 |
| `name` | 姓名 |
| `phone` | 原始手机号（只落库，不通过 API 返回） |
| `gender` | 性别 |
| `dorm_building` / `dorm_room` | 宿舍楼 / 房间 |
| `campus` | 校区（可空） |
| `status` | `active` / `missing_id` / `retained` / `retaking` / `not_arrived` |
| `notes` | 原始异常字段说明，例如“复读”“港澳台/未报到” |
| `source_file` / `source_row` | 来源文件与行号 |
| `import_batch_id` | 导入批次 |

唯一索引：`(cohort, college, student_id)`，因此同一学院同一届的同一学号只会有一条；重复导入会更新。

表 `import_batches` 记录每次导入的文件、批次、数量、跳过与需关注数量，接口 `GET /students/imports` 可查。

---

## 4. 状态如何处理

| 原始情况 | 状态 | 说明 |
|---|---|---|
| 10 位学号、正常 | `active` | 在籍 |
| 学号为空/非 10 位 | `missing_id` | 仍入库，页面显示“待补学号” |
| 楼宇为“（保留入学资格）” | `retained` | 保留资格 |
| 手机号字段含“复读” | `retaking` | 复读 |
| 手机号字段含“港澳台/不来” | `not_arrived` | 未报到 |

这些记录不会被丢弃，方便辅导员后续补齐；不会因为一条脏数据导致整批导入失败。

---

## 5. 与补办流程的关系

`student.query_profile` 先查 20 个演示学号，再查学生库：

- 命中名册：返回姓名、学院、专业、班级、届别，`source = roster`；
- 名册学生的 **一卡通挂失/余额** 没有真实来源，默认按“未挂失、余额 0、无欠费”处理，并标记 `simulated_card_state = true`；
- 确认卡片会显示“学生库：姓名 · 专业 · 班级”，并提示“一卡通状态为模拟数据”。

真实学号示例：

```text
我要补办校园卡
2527405001，天赐庄
```

会带出该生的姓名 / 专业 / 班级，确认后生成回执。

---

## 6. 隐私与上线前必须补的

- 当前是本地课程原型：`registry/students.db` 含原始手机号，**不要提交到公开仓库、不要外发**。
- API 只返回 `phone_masked`（`136****7843`），不返回原始手机号。
- 上线前需要：统一身份认证、RBAC/ABAC、字段级加密、访问审计、数据保留策略、学生授权/告知。
- 真实一卡通、教务、宿舍系统接入后，才可以把“挂失/余额/宿舍”等作为业务依据；当前这些仍是模拟。

---

## 7. 常用接口

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/v1/students/stats` | 总人数、学院/届/班级/专业、状态分布、最近导入 |
| GET | `/api/v1/students?college=...&cohort=...&major=...&q=...` | 分页检索 |
| GET | `/api/v1/students/{student_id}` | 按学号查详情（脱敏） |
| GET | `/api/v1/students/imports` | 导入批次 |

界面入口：左侧导航「学生库」（仅辅导员、审计员、管理员可见）。学生角色只能按自己的学号查询详情，不能列出全量名册。
