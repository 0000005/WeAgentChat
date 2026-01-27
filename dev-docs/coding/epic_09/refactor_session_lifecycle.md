# 重构计划：会话生命周期模块抽取

> **来源**: Story 09-09 技术实现建议  
> **优先级**: Low (后续迭代)  
> **关联验收标准**: AC-1, AC-2

## 背景

当前单聊和群聊的会话生命周期管理（被动超时判定、手动新建会话）逻辑分别实现在两个服务中：
- `chat_service.py`: `get_or_create_session_for_friend()`
- `group_chat_service.py`: `get_or_create_session_for_group()`

两者代码结构高度相似，仅在会话结束时的回调行为不同：
- **单聊**: 触发 Memobase 记忆归档
- **群聊**: 不触发任何记忆归档

## 目标

抽取通用的 `SessionLifecycleManager` 模块，通过回调钩子实现差异化逻辑，降低代码重复和维护成本。

## 设计方案

### 1. 新增模块位置

```
server/app/services/session_lifecycle.py
```

### 2. 接口设计

```python
from typing import Optional, Callable, TypeVar, Generic
from sqlalchemy.orm import Session as DBSession
from datetime import datetime, timezone

T = TypeVar('T')  # Session model type (ChatSession or GroupSession)

class SessionLifecycleManager(Generic[T]):
    """
    通用会话生命周期管理器。
    支持被动超时判定和手动新建会话，通过回调钩子注入差异化结束逻辑。
    """
    
    def __init__(
        self,
        get_active_session: Callable[[DBSession, int], Optional[T]],
        create_session: Callable[[DBSession, int, Optional[str]], T],
        on_session_end: Optional[Callable[[DBSession, T], None]] = None,
        session_type_name: str = "Session"  # 用于日志
    ):
        self.get_active_session = get_active_session
        self.create_session = create_session
        self.on_session_end = on_session_end  # 回调钩子
        self.session_type_name = session_type_name

    def get_or_create_session(
        self, 
        db: DBSession, 
        target_id: int, 
        timeout_seconds: int = 1800
    ) -> T:
        """
        获取或创建会话。
        如果当前会话已超时，则结束当前会话（触发回调）并创建新会话。
        """
        session = self.get_active_session(db, target_id)
        
        if session:
            if session.last_message_time:
                now_time = datetime.now(timezone.utc)
                elapsed = (now_time - session.last_message_time).total_seconds()
                
                if elapsed > timeout_seconds:
                    self._end_session(db, session, reason="EXPIRED")
                    session = None
                    
        if not session:
            session = self.create_session(db, target_id, None)
            
        return session

    def create_new_session(self, db: DBSession, target_id: int) -> T:
        """
        手动创建新会话，结束所有活跃会话。
        """
        # 需要由调用方提供批量获取活跃会话的能力
        # 或直接在此处查询
        raise NotImplementedError("Override in subclass or use partial")

    def _end_session(self, db: DBSession, session: T, reason: str = ""):
        """
        结束会话，触发回调钩子。
        """
        session.ended = True
        session.update_time = datetime.now(timezone.utc)
        
        callback_info = "(NO callback)" if self.on_session_end is None else "(with callback)"
        logger.info(f"[{self.session_type_name}] Session {session.id} ended: {reason} {callback_info}")
        
        if self.on_session_end:
            self.on_session_end(db, session)
        
        db.commit()
```

### 3. 使用示例

#### 单聊服务

```python
from app.services.session_lifecycle import SessionLifecycleManager
from app.services.memo.bridge import MemoService

def _on_chat_session_end(db, session):
    """单聊会话结束回调：触发记忆归档"""
    asyncio.create_task(MemoService.extract_and_archive(session))

chat_lifecycle = SessionLifecycleManager(
    get_active_session=ChatSessionService._get_active_session,
    create_session=ChatSessionService._create_session,
    on_session_end=_on_chat_session_end,
    session_type_name="ChatSession"
)
```

#### 群聊服务

```python
group_lifecycle = SessionLifecycleManager(
    get_active_session=GroupChatService._get_active_group_session,
    create_session=GroupChatService._create_group_session,
    on_session_end=None,  # 不触发任何记忆归档
    session_type_name="GroupSession"
)
```

### 4. 迁移步骤

1. **Phase 1**: 创建 `session_lifecycle.py` 基础框架
2. **Phase 2**: 迁移 `group_chat_service.py` 使用新模块（风险较低）
3. **Phase 3**: 迁移 `chat_service.py` 使用新模块（涉及记忆归档，需充分测试）
4. **Phase 4**: 删除原有重复代码

### 5. 验收标准

- [ ] 单聊被动超时仍正确触发记忆归档
- [ ] 群聊被动超时**不**触发记忆归档
- [ ] 手动新建会话行为与重构前一致
- [ ] 日志格式统一且清晰
- [ ] 单元测试覆盖率不降低

## 风险评估

| 风险 | 概率 | 影响 | 缓解措施 |
|------|------|------|----------|
| 记忆归档逻辑回归 | 中 | 高 | 充分的集成测试 |
| 类型系统兼容性 | 低 | 低 | 使用 Generic 泛型 |
| 异步回调协调 | 中 | 中 | 明确同步/异步边界 |

## 时间估算

- **实现**: 2-3 小时
- **测试**: 1-2 小时
- **总计**: 约半天

---

*创建日期*: 2026-01-27  
*最后更新*: 2026-01-27
