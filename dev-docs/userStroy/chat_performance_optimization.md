# Story: 聊天加载优化与缓存

## 背景
目前，当用户在侧边栏点击好友时：
1. 系统会直接从后端 API 获取聊天记录（`getFriendMessages`，默认限制 200 条）。
2. 每次切换好友时，用户都会体验到"重新渲染"的卡顿或加载状态。
3. 即使数据已经在内存中，系统仍会发送冗余的网络请求。

## 目标
通过优化聊天加载策略来提高应用的响应速度：
1. 实现分页功能，初始只加载少量消息。
2. 利用本地缓存，避免冗余的网络请求。

## 需求

### 1. 聊天记录分页
**问题**：一次性加载 200 条消息会导致渲染延迟。
**需求**：
- 点击好友时，初始只加载最近的 **30 条消息**（可通过常量配置，如 `INITIAL_MESSAGE_LIMIT = 30`）。
- **滚动加载**：当用户**向上滚动到顶部**时，加载更早的消息（分页）。
- **滚动位置保持**：加载历史消息后，保持用户当前的滚动位置，避免"跳顶"。

### 2. 本地缓存（好友与消息）
**问题**："点击好友时去走 http 请求拿取最新的好友" → 每次点击都会触发请求。
**需求**：
- **优先检查缓存**：选择好友（`selectFriend`）时，首先检查 `sessionStore` 中是否已存在 `messagesMap[friendId]`。
- **命中策略**：
    - 如果 `messagesMap` 中存在数据：**立即**渲染，无需等待网络请求。
    - **好友详情**：确保好友元数据（头像、名称）从 `friendStore`（已缓存）读取，不再触发单独的实体获取请求。
- **静默同步（Silent Sync）**：
    - 即使命中缓存，也应在后台触发一次轻量级请求（`skip=0, limit=10`，获取最新 10 条消息），以检查是否有**异步接收**的新消息。
    - 前端通过 `id` 比对去重，将新消息追加到缓存末尾，静默更新 UI。
    - *注*：当前后端 API 不支持 `since_id` 参数，MVP 阶段使用 `skip/limit` + 前端去重实现。后续可考虑新增 `since_id` 支持以提高效率。
- **缓存失效策略**：
    - `messagesMap[friendId]` 在以下情况下被清空：
        - 用户调用 `clearFriendHistory(friendId)` 清空聊天记录。
        - 用户删除好友。
        - 应用重启/刷新页面（内存缓存，非持久化）。

### 3. 边缘情况：异步消息同步
**问题**：在"双轨记忆"和"Agent 社交"系统中，消息接收可能是异步的（非用户主动请求触发）。如果仅依赖静态缓存，用户可能错过后台发生的重要上下文或错误信息。
**需求**：
- **场景 A：流式传输中断恢复**：如果用户在消息流式传输（SSE）过程中切换了好友，后台可能仍在接收数据或报错。再次切回该好友时，缓存中的数据可能是不完整的。
    - **对策**：切换回好友时，通过静默同步获取最新消息。由于 SSE `done` 事件已将完整消息写入缓存，静默同步会自动补齐可能遗漏的最终状态。
- **场景 B：后台推送/多端同步**：如果有后台任务（如 Agent Moment 互动）向该好友插入了新消息。
    - **对策**：`selectFriend` 时的"静默同步"机制通过比对 `id` 检测新消息并追加。
- **错误处理**：
    - 静默同步失败（网络错误）时，**不阻塞 UI**，仅在 console 记录警告。
    - 用户可通过**下拉刷新**（未来实现）手动重试。

### 4. 未来扩展（P1/P2）
- **实时推送**：接入 WebSocket 或利用现有 SSE 通道监听新消息事件，实现真正的实时同步（而非轮询/手动触发）。
- **持久化缓存**：使用 IndexedDB 或 localStorage 持久化 `messagesMap`，支持离线查看和更快的冷启动。

## 实现任务

### 前端 (`front/src/stores/session.ts`)
1.  **修改 `fetchFriendMessages`**：
    -   增加对 `skip` 和 `limit` 参数的支持。
    -   新增常量 `INITIAL_MESSAGE_LIMIT = 30`。
2.  **新增 `loadMoreMessages(friendId: number)` 动作**：
    -   计算当前 `skip = messagesMap.value[friendId]?.length || 0`。
    -   调用 API 获取更早的消息，并**前置**到数组。
    -   返回布尔值表示是否还有更多历史消息（用于 UI 显示"已无更多"）。
3.  **新增 `syncLatestMessages(friendId: number)` 动作（静默同步）**：
    -   调用 `getFriendMessages(friendId, 0, 10)` 获取最新 10 条。
    -   与 `messagesMap[friendId]` 比对，追加不存在的新消息。
    -   不触发 `isLoading` 状态。
4.  **更新 `selectFriend` 逻辑**：
    ```typescript
    const selectFriend = async (friendId: number) => {
      currentFriendId.value = friendId
      // 清除未读计数
      if (unreadCounts.value[friendId]) {
        unreadCounts.value[friendId] = 0
      }
      currentSessionId.value = null

      // 命中缓存：立即渲染，后台静默同步
      if (messagesMap.value[friendId]?.length > 0) {
        // 不设置 isLoading，UI 立即可用
        // 后台静默同步（不 await）
        syncLatestMessages(friendId).catch(e => console.warn('Silent sync failed:', e))
        fetchFriendSessions(friendId) // 会话列表也静默刷新
        return
      }

      // 缓存未命中：显示加载状态
      isLoading.value = true
      try {
        await Promise.all([
          fetchFriendMessages(friendId, 0, INITIAL_MESSAGE_LIMIT),
          fetchFriendSessions(friendId)
        ])
      } finally {
        isLoading.value = false
      }
    }
    ```

### 前端 (`front/src/components/ChatArea.vue`)
1.  **滚动处理**：
    -   在 `<ConversationContent>` 外层监听 `@scroll` 事件。
    -   检测 `scrollTop < 50`（接近顶部）时，触发 `loadMoreMessages`。
    -   使用 `scrollHeight` 差值计算，加载后恢复滚动位置。
    -   添加节流（throttle）防止频繁触发。
2.  **加载状态**：
    -   新增 `isLoadingMore` 状态，用于在顶部显示"加载中..."提示。
    -   当 `loadMoreMessages` 返回 `false`（无更多历史）时，显示"已无更多消息"。

### 后端 (`server/`)
-   *注*：后端 API `GET /api/chat/friends/{friend_id}/messages` 已支持 `skip` 和 `limit`。本次无需更改。
-   **P1 优化（可选）**：新增 `since_id` 查询参数，返回 `id > since_id` 的消息，提升静默同步效率。

## 验收标准
- [ ] 点击曾经查看过的好友时，聊天界面**瞬间**切换（< 50ms），使用缓存数据。
- [ ] 首次点击未访问的好友时，仅加载最近 30 条消息，并显示 Loading 状态。
- [ ] 即使在离线/网络断开情况下，已缓存的好友聊天也能查看。
- [ ] 如果在切换好友期间产生了新消息，再次点击该好友时，新消息会静默追加到底部。
- [ ] 向上滚动到顶部时，触发加载更早的消息（分页），并保持滚动位置。
- [ ] 清空聊天记录后，缓存同步清除。
- [ ] 静默同步失败时，不阻塞 UI，不显示错误弹窗。
