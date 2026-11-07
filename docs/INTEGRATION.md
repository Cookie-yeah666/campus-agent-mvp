# 登录、RBAC 与真实校园接口适配

## 1. 演示账号

| 账号 | 密码 | 角色 | 可见范围 |
|---|---|---|---|
| `admin` | `admin123` | 管理员 | 全部 |
| `counselor` | `counselor123` | 辅导员 | 本学院学生、本学院/共享会话、审计 |
| `auditor` | `auditor123` | 审计员 | 全量只读、学生库脱敏、系统状态 |
| 名册学号 | 学号后六位 | 学生 | 自己的会话/工单、知识问答、评测 |

学生登录输入 **学号 + 姓名 + 密码**，姓名必须与 `registry/students.db` 一致；密码初值为学号后六位。工作人员账号可直接点登录页的演示按钮。

> 演示密码只用于课程原型。生产必须接 CAS/OAuth2、HTTPS、登录限流、密钥管理。

## 2. 权限实现

- Token：HMAC-SHA256 自包含 Token，默认 8 小时，无 JWT 依赖。
- 工作人员密码：PBKDF2-HMAC-SHA256，12 万次迭代，随机盐，只在内存校验。
- 学生密码：初值为学号后六位，登录时与名册学号实时比对；未单独存密码哈希。生产必须改为统一身份认证并强制改密。
- 会话：`ChatSession.owner_id / owner_role / owner_college`。
- 工单：通过所属会话判断，避免绕过会话直接查工单。
- 学生库：学生只能查自己；辅导员强制本学院；审计员/管理员全量。
- 审计：学生/辅导员只返回可见会话事件；审计员/管理员全量。
- 系统状态：仅审计员/管理员。

认证关闭：`CAMPUS_AUTH_ENABLED=false` 时退化为匿名管理员，供 pytest 使用。

## 3. 真实接口适配

默认：

```env
CAMPUS_INTEGRATION_MODE=mock
```

切到 HTTP：

```env
CAMPUS_INTEGRATION_MODE=http
CAMPUS_INTEGRATION_BASE_URL=https://your-campus-gateway.example/api
CAMPUS_INTEGRATION_API_KEY=replace-me
CAMPUS_INTEGRATION_TIMEOUT_SECONDS=8
```

`app/integrations/http_campus.py` 约定的契约：

| 能力 | 方法 | 路径 |
|---|---|---|
| 学籍 | GET | `/students/{student_id}` |
| 校园卡状态/余额 | GET | `/students/{student_id}/card` |
| 挂失 | POST | `/students/{student_id}/card/loss` |
| 时段 | GET | `/card/slots?campus=天赐庄` |
| 提交补办 | POST | `/card/reissue` |

提交补办请求体：

```json
{
  "student_id": "2527405001",
  "campus": "天赐庄",
  "slot_id": "2026-11-06-AM",
  "idempotency_key": "card_reissue:2527405001:2026-11-06",
  "fee": 20.0
}
```

响应至少包含 `receipt_number` 与 `status`；其余字段会透传给前端工单卡片。

### 接入新学校的步骤

1. 让校方提供网关地址、认证方式、字段字典和测试账号。
2. 先只接 **一个只读接口 + 一个写接口沙箱**，不要一次接全。
3. 在 `HttpCampusService` 的 `query_profile / _card / query_available_slots / submit_reissue_order` 中改字段映射。
4. 用 `httpx.MockTransport` 写契约测试，再接沙箱联调。
5. 生产补齐超时、重试、幂等、对账、告警与审计。

> 当前没有真实接口文档/测试账号，所以 HTTP 适配器只完成契约映射和单元测试，**没有真实联调**；默认仍走 Mock。

## 4. 安全上线清单

- 统一身份认证（CAS/OAuth2）与 HTTPS。
- RBAC/ABAC + 字段级加密 + 数据保留策略。
- 登录失败限流、Token 撤销、密钥轮换。
- 审计防篡改（哈希链）与导出审批。
- 真实一卡通/教务/宿舍系统接入后，才把余额、挂失、宿舍作为业务依据。
