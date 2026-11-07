# 流程 DSL：从硬编码到可复制流程

## 1. 现在有什么

流程定义在：

```text
workflows/
├─ card_reissue.json     # 校园卡补办，16 节点 / 16 边
└─ network_repair.json   # 网络报修，7 节点 / 6 边
```

加载器：`app/workflow/dsl.py`  
注册表：`app/workflow/definitions.py`

新增流程 = 新增一个 JSON + 需要的工具/条件，不改引擎。

---

## 2. 最小 DSL 结构

```json
{
  "id": "network_repair",
  "name": "网络报修",
  "version": "1.0.0",
  "start_node": "start",
  "nodes": [
    {"id": "start", "name": "开始", "node_type": "start", "config": {}},
    {"id": "extract", "name": "确认信息", "node_type": "parameter_extract", "config": {"fields": ["student_id", "campus"]}},
    {"id": "create", "name": "生成报修单", "node_type": "tool_call", "config": {"tool": "repair.create_ticket", "arguments": {"student_id": "$student_id", "campus": "$campus"}, "save_as": "repair_ticket"}},
    {"id": "confirm", "name": "人工确认", "node_type": "confirmation", "config": {"message_template": "确认报修？{student_id} {campus}"}},
    {"id": "submit", "name": "提交", "node_type": "tool_call", "config": {"tool": "repair.submit_ticket", "arguments": {"ticket_id": "$repair_ticket_id", "idempotency_key": "$idempotency_key"}, "save_as": "order", "idempotent": true}},
    {"id": "done", "name": "完成", "node_type": "result", "config": {"result_kind": "success", "message_template": "已受理：{receipt}"}}
  ],
  "edges": [
    {"source": "start", "target": "extract"},
    {"source": "extract", "target": "create"},
    {"source": "create", "target": "confirm"},
    {"source": "confirm", "target": "submit", "condition": "confirmed"},
    {"source": "confirm", "target": "done", "condition": "cancelled"},
    {"source": "submit", "target": "done"}
  ]
}
```

第一版支持的节点类型：

| 类型 | 用途 |
|---|---|
| `start` | 入口 |
| `parameter_extract` | 抽取学号/校区/报修类型/描述 |
| `tool_call` | 调用注册工具 |
| `condition` | 按注册条件分支 |
| `confirmation` | 人工确认/取消 |
| `result` | 结束并返回回执/失败信息 |
| `human_handoff` | 转人工 |
| `end` | 结束 |

暂不支持：并行分支、定时器、可视化编排、复杂补偿。

---

## 3. 版本与快照

工单创建时保存：

- `definition_version`：定义版本号；
- `definition_snapshot`：整份定义快照。

恢复工单时优先用快照，因此：

- 流程升级后，老工单仍按老版本跑；
- 新工单按新版本跑；
- 不会出现“上线新版本，老工单一半走新节点”的事故。

实现位置：`app/workflow/engine.py` 的 `start` / `resume`。

---

## 4. 如何新增一条流程

1. 在 `workflows/` 新建 JSON；
2. 复用现有工具，或新增 `@register_tool`；
3. 复用现有条件，或在 `app/workflow/conditions.py` 注册；
4. 启动时 `load_workflows()` 自动加载；
5. 在 `WorkflowAgent` 中把用户意图映射到流程 id；
6. 加测试：成功、取消、缺参数、工具失败。

不改 `WorkflowEngine` 本身。

---

## 5. 当前两条流程

### 校园卡补办

```text
start → extract_params → query_profile → check_profile
 → query_loss → check_loss → (report_loss) → query_balance
 → check_arrears → query_slots → confirm → submit_order → result_success
```

### 网络报修

```text
start → extract_params → repair.create_ticket → confirm
 → repair.submit_ticket → result_success
```

网络报修用的工具：

- `repair.create_ticket`：生成待确认报修单；
- `repair.submit_ticket`：提交、幂等、返回 RPR 回执。

当前都是 Mock 工具，真实派单系统还没接。

---

## 6. 请假流程

`workflows/leave.json`：

```text
start → extract_params → leave.create_request
 → approval_counselor
   → 通过且 >3 天 → approval_college → leave.submit_request → result_success
   → 通过且 ≤3 天 → leave.submit_request → result_success
   → 驳回 → result_rejected
```

审批节点 `node_type=approval`：

- 第一次执行暂停，工单状态 `awaiting_approval`；
- 工作人员通过 `POST /api/v1/approvals/{id}/approve` 或 `/reject` 恢复；
- 一次审批只消费一次 `confirmed`，超过 3 天必须再次学院审批；
- 审批通过后生成 `LVE` 回执；
- 审批前学生可调用 `POST /api/v1/approvals/{id}/withdraw` 撤回，工单转为 `cancelled`；
- 通过后学生可调用 `POST /api/v1/approvals/{id}/return` 销假，Mock 请假单转为 `returned`。

当前审批是 Mock 业务，没有真实教务/学工审批系统。

## 7. 下一步

- 请假撤回、销假；
- 流程版本管理页面；
- 仿真回放；
- 真实报修/请假系统适配。
