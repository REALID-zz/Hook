# API 契约（首版）

目标：为 Web/PWA MVP 定义稳定的 API 形状，后端先单体实现，后续可拆分服务。

## 1) 约定

- 所有时间使用 ISO8601 字符串（UTC）。
- 位置仅用 `venueId` + `timeWindow`（首版不做持续定位）。
- 首版鉴权可先用“匿名用户 + session cookie”，后续升级为 JWT/OAuth。

## 2) 数据对象（简化版）

### 2.1 Venue
```json
{ "id": "v_hk_001", "name": "Central_ExampleCafe", "city": "HongKong" }
```

### 2.2 Post（邀约/失物/招领）
```json
{
  "id": "p1",
  "type": "invite",
  "title": "在Central一起吃饭",
  "body": "…",
  "venueId": "v_hk_001",
  "startAt": "2026-02-21T12:00:00Z",
  "endAt": "2026-02-21T14:00:00Z",
  "tags": ["eat","help"],
  "visibility": "venue_only",
  "safetyLevel": "normal"
}
```

### 2.3 ChatMessage（WebSocket）
```json
{ "type": "msg", "text": "hello", "ts": "2026-02-21T12:00:00Z" }
```

## 3) REST endpoints（首版）

### 3.1 场所
- `GET /api/venues`

### 3.2 Posts
- `GET /api/posts?venueId=...&type=invite|lost|found`
- `POST /api/posts`
  - body: `PostCreate`
- `GET /api/posts/{postId}`

### 3.3 失物匹配（首版：推荐）
- `GET /api/lost/suggestions?venueId=...&postId=...`

### 3.4 项目（占位）
- `GET /api/projects`
- `POST /api/projects`（后续）

### 3.5 市集（占位）
- `GET /api/listings`
- `POST /api/listings`（后续）

## 4) WebSocket（实时）

### 4.1 连接
- `GET /ws/chat?room=venue:{venueId}`

### 4.2 事件
- `system`: 加入/离开提示
- `msg`: 文本消息

> 后续可扩展：typing、presence、message_ack、moderation_flag、room_join/leave 等。

