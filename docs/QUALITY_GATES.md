# 质量门禁与评测基线

## 1. 当前基线

| 项 | 当前值 | 说明 |
|---|---:|---|
| pytest | 76 passed | 功能 + 权限 + 学习 + 审计链 + 注入 + 撤回 |
| 检索集 | 180 可答 + 60 越界 | 300 silver |
| Recall@5 | 1.0000 [0.9791, 1.0000] | 可答 180 |
| MRR@5 | 0.9935 | — |
| nDCG@5 | 0.9952 | — |
| Hard-negative FPR | 0.0389 | **已达标**（≤0.10） |
| 越界误答率 | 0.0167 | **已达标**（≤0.05） |
| 引用存在率 | 0.9667 | MockLLM |
| 拒答准确率 | 0.9833 | **已达标**（≥0.95） |
| 任务成功率 | 20/20 [0.8389, 1.0000] | 20 条 |

## 2. 建议门禁

### PR 快速门禁

```bash
python -m pytest -q
python scripts/evaluate.py --suite retrieval --split dev
```

失败条件：

- 任一测试失败；
- dev Recall@5 < 0.90；
- 新增权限接口没有对应测试。

### Nightly

```bash
python scripts/evaluate.py --suite all --split test \
  --output reports/eval-nightly.json
```

失败条件：

- Recall@5 < 0.90；
- MRR@5 < 0.80；
- Hard-negative FPR > 0.10；
- 越界误答率 > 0.05；
- 任务成功率 < 18/20；
- 重复提交新增工单 > 0。

### Release

- 全量 pytest；
- 300 silver + 20 任务；
- 权限回归（`tests/test_security_api.py`）；
- 人工抽检 20%；
- 报告与 commit hash 绑定。

## 3. 本轮改善与剩余风险

1. Hard-negative FPR 已从 13.3% 降到 3.89%：相对分数截断 0.55，Recall@5 保持 1.0；
2. 越界误答已从 6.7% 降到 1.67%，达标；
3. 拒答准确率已从 93.3% 升到 98.33%，达标；
4. 剩余风险：300 条是 silver，不是人工金标；生成质量仍是 MockLLM；相对截断需要真实 LLM 下复测。

## 4. 安全回归

`tests/test_security_api.py` 覆盖：

- 未登录访问会话 401；
- 学生访问他人会话 403；
- 学生访问他人学生记录 403；
- 学生列全量学生库 403；
- 学生访问坐席/审批队列 403；
- 辅导员访问坐席/审批队列 200；
- 手机号脱敏；
- Token 篡改 401；
- Prompt 注入拦截；
- 审计哈希链正常校验 + 篡改检测。

## 5. 未完成

- Prompt 注入红队（已有基础拦截，仍需扩展语料）；
- 权限感知检索；
- 审计哈希链外部锚定/只追加存储；
- LLM-as-judge 与人工校准；
- 端到端任务 20 条的独立人工复核。
