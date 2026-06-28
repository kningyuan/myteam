---
name: API设计方法论
description: API设计方法论：RESTful规范、资源建模、版本管理、错误处理、认证鉴权与文档规范，产出可用的API设计文档。
---
# API设计方法论

## 任务描述
设计 RESTful API 接口规范，覆盖资源建模、URL设计、请求/响应格式、错误处理、认证鉴权、版本管理与文档规范。

## 设计原则

### 1. 资源建模
- **名词复数** — `/users`, `/orders`, `/products`（不用动词）
- **层级关系** — `/users/{id}/orders`（用户下的订单）
- **扁平化优先** — 层级不超过 3 级
- **资源 vs 操作** — CRUD用HTTP方法表达，非CRUD用子资源或action

### 2. URL规范

| HTTP方法 | URL | 语义 | 幂等 |
|----------|-----|------|------|
| GET | `/resources` | 列表 | 是 |
| GET | `/resources/{id}` | 详情 | 是 |
| POST | `/resources` | 创建 | 否 |
| PUT | `/resources/{id}` | 全量更新 | 是 |
| PATCH | `/resources/{id}` | 部分更新 | 否 |
| DELETE | `/resources/{id}` | 删除 | 是 |

- **query参数**：分页(`page`/`per_page`)、过滤(`?status=active`)、排序(`?sort=-created_at`)、字段(`?fields=id,name`)
- **路径参数**：仅用于资源标识（`{id}`），不传业务参数
- **禁止**：URL中放动词（`/getUser`）、大写、下划线

### 3. 请求/响应格式

**请求**：
```json
{
  "name": "string",
  "price": 100,
  "tags": ["string"]
}
```

**成功响应**（统一信封）：
```json
{
  "code": 0,
  "message": "success",
  "data": { ... },
  "meta": { "page": 1, "per_page": 20, "total": 100 }
}
```

**错误响应**：
```json
{
  "code": 40001,
  "message": "参数校验失败",
  "errors": [
    { "field": "price", "message": "必须大于0" }
  ]
}
```

### 4. 错误码设计

| 区间 | 类别 | 示例 |
|------|------|------|
| 0 | 成功 | 0 |
| 10000-19999 | 通用错误 | 10001 参数校验失败 |
| 20000-29999 | 认证授权 | 20001 未登录, 20003 无权限 |
| 30000-39999 | 业务错误 | 30001 余额不足 |
| 40000-49999 | 资源错误 | 40001 资源不存在 |
| 50000-59999 | 系统错误 | 50001 内部异常 |

### 5. 认证与鉴权
- **Bearer Token** — `Authorization: Bearer <token>`
- **API Key** — `X-API-Key: <key>`（仅限内部服务）
- **OAuth 2.0** — 第三方授权场景
- **RBAC** — 基于角色的权限控制
- **速率限制** — `X-RateLimit-Limit` / `X-RateLimit-Remaining`

### 6. 版本管理
- **URL版本** — `/v1/users`, `/v2/users`（推荐）
- **向后兼容** — 新版本不破坏旧版本的调用方
- **废弃策略** — 标记 `Deprecation: true` 响应头，给3个月迁移期

## 必选章节
- 资源模型（含关系图）
- API 列表（含方法/URL/请求体/响应体/状态码）
- 错误码表
- 认证方案
- 版本管理策略
- 分页/过滤/排序规范

## Gate 规则
- 每个API须有请求体和响应体示例
- 错误码须覆盖所有非成功场景
- 认证方案须有具体Header示例
- 须有版本管理策略，不能只写"后续考虑"
