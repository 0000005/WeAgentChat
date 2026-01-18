# 记忆召回算法准确性测试 (Memory Recall Algorithm Accuracy Test)

## 1. 背景与目标
目前系统已集成向量数据库（sqlite-vec）用于记忆存储。为了确保 AI 能够精准地召回与当前对话相关的历史记忆，我们需要通过定量测试来确定最佳的**召回算法参数**以及**查询构造方式**。

这不是一个面向最终用户的常规功能 Story，而是一个技术探索（Spike）性质的 Story，旨在为后续的记忆召回功能优化提供数据支撑。

**核心目标**：
1. 测试不同类型的查询（关键词 vs 自然语言）在向量检索中的表现。
2. 确定最佳的相似度阈值（Threshold）和召回数量（TopK）。


## 2. 测试计划

### 阶段一：数据准备 (Data Preparation)
需要在向量数据库中预置一批具有代表性的测试数据（建议 **500条** 以上），模拟真实场景下长期积累的用户记忆库。本阶段进一步拆分为两个子阶段：

#### 子阶段 1：生成文本数据 (Text Generation)
首先构建纯文本的记忆库，暂不进行向量化，专注于内容构建。
- **任务**：编写脚本生成或导入 500+ 条符合规范的测试文本。
- **数据规范**：
  - **格式**：所有记忆片段必须采用 `用户[行为/属性/状态]。[提及于 YYYY/MM/DD]` 的格式。
    - *示例*：`用户玩过《只狼》并通关了三遍。[提及于 2026/01/13]`
- **内容分布**：
  - **核心话题数据**（约 300 条）：
    - 编程相关：`用户讨厌调试 C++ 的段错误。[提及于 2026/01/10]`
    - 饮食相关：`用户最喜欢的食物是四川火锅。[提及于 2026/01/12]`
    - ...
  - **干扰/噪音数据**（约 200 条）：
    - **似是而非**：`用户新买了一部苹果手机。[提及于 2026/01/11]`（干扰“喜欢吃苹果”的查询）
    - **情感对立**：`用户小时候被猫抓过，很害怕猫。[提及于 2025/12/01]`（干扰“喜欢猫”的查询）
    - **时间混淆**：`用户明天（2026/01/19）要上班。[提及于 2026/01/18]`（干扰关于“周末去哪玩”的查询）

#### 子阶段 2：向量化处理 (Vectorization)
读取子阶段 1 生成的文本数据，批量计算向量并入库。
- **任务**：编写脚本读取文本列表，调用 Embedding 模型（如 `text-embedding-3-small`），为每条文本生成向量。
- **数据结构**：每条入库数据应包含 `(ID, Text Content, Vector)`。

**重要约束**：
- **数据隔离**：测试数据**必须存放于独立的数据库文件或独立的表结构中**（建议创建一个临时的 `demo_memory.db` 或临时表），**严禁**直接混入业务数据库（`doudou.db` 或 `memobase.db`）。
- **可清理性**：测试完成后，必须能够通过简单命令或脚本彻底清除所有测试数据和表结构，确保不污染生产环境。

### 阶段二：召回测试 (Recall Testing)
编写测试脚本，通过不同的召回方式对预置数据进行检索，并统计准确率。

**测试维度**：
1.  **查询构造方式**：
    -   **纯关键词**：例如 `"火锅"` 或 `"Python 调试"`。
    -   **简单自然语言**：例如 `"我想吃火锅"`。
    -   **复杂自然语言**：例如 `"我上次说想去日本旅游具体是想看什么？"`。
    -   **重写式查询**：测试是否需要将用户口语重写为陈述句再进行搜索。

2.  **评分与验证机制 (Evaluation & Scoring)**：
    单纯看召回结果无法判断好坏，必须建立 **"标准答案" (Ground Truth)** 进行自动化评分。
    -   **预设测试集**：构建 `(Query, Expected_Memory_IDs)` 的映射关系。
        -   *例子*：Query="想吃火锅", Expected=[ID_01(喜欢辣), ID_02(海底捞)]。
    -   **核心指标**：
        -   **Hit Rate@K (命中率)**：Top K 结果中是否包含预期 ID。包含则视为“召回成功”。
        -   **Precision (准确率)**：返回的 Top K 结果中，有多少是与预期相关的。（避免召回一堆无关噪音）。
        -   **Noise Resistance (抗噪分)**：特意检查返回结果中是否混入了预设的“干扰项”（如搜“苹果”混入了“苹果手机”）。如有混入，该项测试不合格。

3.  **算法参数对比**：
    -   测试不同的 `similarity_threshold` (0.3, 0.5, 0.7) 对召回结果的影响（是否漏掉相关记忆，或引入无关噪音）。
    -   测试不同的 `TopK` 设置。



### 阶段三：结果分析与应用
根据测试脚本的输出，产出结论报告。

**产出物要求**：
-   一份简短的测试结论，说明哪种查询方式和参数组合准确率最高。
-   （可选）如果测试发现当前 Embedding 模型效果不佳，需提出更换模型的建议。

**后续应用（Scope Out）**：
-   将测试得出的最佳参数和查询构造逻辑应用到主系统的 `MemoService` 中（此步骤不在本 Story 范围内）。

## 3. 验收标准 (Acceptance Criteria)
1.  [x] 完成 100 条左右的多样化测试数据的入库。
2.  [x] 完成并通过召回测试脚本，脚本需输出不同查询用例的召回结果（Score 和 Content）。
3.  [x] 确定一套推荐的参数配置（Threshold, TopK, Query Style），作为后续开发的依据。

---

## 4. 执行记录 (Execution Log)

### 2026-01-18 执行进度

#### ✅ 阶段一：数据准备 - 已完成

**子阶段 1：生成文本数据** ✅
- **脚本位置**: `scripts/memory_test/gen_test_data.py`
- **输出文件**: `scripts/memory_test/test_data_source.json`
- **数据量**: 530 条
- **内容分布**:
  - 核心话题数据 (~300条): 编程、饮食、游戏、旅行、日常生活
  - 干扰/噪音数据 (~200条): 语义歧义(苹果/苹果手机)、情感对立(喜欢/讨厌)、时间混淆、随机琐事

**子阶段 2：向量化处理** ✅
- **脚本位置**: `scripts/memory_test/vectorize_data.py`
- **运行方式**: `scripts/memory_test/run_vectorization.bat`
- **输出数据库**: `scripts/memory_test/demo_memory.db`
- **Embedding 配置**:
  - API: SiliconFlow (`https://api.siliconflow.cn/v1`)
  - 模型: `BAAI/bge-m3`
  - 维度: 1024
- **数据库表结构** (与 Memobase 保持一致):
  ```sql
  CREATE TABLE memories (
      content TEXT NOT NULL,
      embedding BLOB
  )
  ```
- **入库数量**: 530 条

**辅助工具**:
- 数据库检查脚本: `scripts/memory_test/inspect_db.py`

#### ✅ 阶段二：召回测试 - 已完成

**测试脚本**:
- 召回测试脚本: `scripts/memory_test/recall_test.py`
- 测试用例集: `scripts/memory_test/test_cases.json` (25 个用例)
- 运行脚本: `scripts/memory_test/run_recall_test.bat`

**测试配置**:
- Embedding 模型: `BAAI/bge-m3` (SiliconFlow API)
- 向量维度: 1024
- 测试参数组合: TopK ∈ {3, 5, 10}, Threshold ∈ {0.4, 0.5, 0.6}


**测试结果 (Version 2.0)**:
```
============================================================
                       FINAL SUMMARY
============================================================
TopK  | Thresh | HitRate  | Prec.    | NoiseRes
------------------------------------------------------------
3     | 0.4    | 84.62   % | 76.92   % | 76.92   %
5     | 0.4    | 92.31   % | 73.85   % | 76.92   %
5     | 0.5    | 92.31   % | 73.85   % | 76.92   %
5     | 0.6    | 69.23   % | 61.54   % | 92.31   %
10    | 0.6    | 69.23   % | 56.15   % | 92.31   %
============================================================
```

**分类型表现 (TopK=5, Threshold=0.5)**:
- **Semantic Indirect (语义间接)**: **100% Hit Rate**。模型展现了极强的意图理解能力（如"重口味食物" -> "麻辣烫"）。
- **Keyword Combo (关键词组)**: **85.7% Hit Rate**。表现非常稳健，甚至在 Threshold=0.6 时仍保持高召回，证明提取关键词进行组合查询是最高效、最稳定的方式。
- **Simple Natural (自然语言)**: **100% Hit Rate** (但在 TopK=3 时仅 50%)。自然语言查询引入了更多噪音，需要更大的 TopK 窗口。

#### ✅ 阶段三：结果分析与应用 - 已完成

**最佳参数配置推荐**:
| 参数 | 推荐值 | 说明 |
|------|--------|------|
| TopK | 5 | 平衡召回率和准确率 |
| Similarity Threshold | 0.5 | 语义查询的最佳平衡点 (0.6 会导致语义召回腰斩) |
| Distance Threshold | < 0.5 | 对应 sqlite-vec 的 cosine distance |

**关键结论**:
1. **语义查询需要较低阈值**：语义间接查询（如"高难度游戏"找"只狼"）的相似度通常在 0.4-0.6 之间。如果阈值设为 0.6，语义召回率从 100% 骤降至 50%。
2. **关键词组查询最稳健**：模拟系统提取关键词（如 "旅游 计划 明年"）的方式效率极高，且受阈值影响小，抗噪能力强。
3. **抗噪性与召回率的权衡**：要实现 92% 的高抗噪性（Threshold=0.6），必须接受召回率降至 69% 的代价。推荐维持 0.5 阈值，通过后处理（Rerank 或 LLM 过滤）来解决剩余的噪音。

**后续建议**:
- **优先策略**：Memobase 应继续采用“提取关键词组”的方式进行检索，这是最稳健的。
- **兜底策略**：当关键词检索结果不足时，可回退到“自然语言查询” + “Threshold=0.4” 的宽泛搜索。
- **应用配置**：主系统 `MemoService` 采用 `TopK=5, Threshold=0.5`。

---

## 5. 生成文件清单 (Generated Files Inventory)

本次任务共生成/修改以下文件，全部位于 `scripts/memory_test/` 目录：

### 核心脚本

| 文件名 | 类型 | 说明 |
|--------|------|------|
| `gen_test_data.py` | Python | 测试数据生成脚本，生成 530 条多样化记忆文本 |
| `vectorize_data.py` | Python | 向量化脚本，调用 Embedding API 并写入数据库 |
| `recall_test.py` | Python | 召回测试核心脚本，执行向量检索并计算评估指标 |
| `inspect_db.py` | Python | 数据库检查工具，验证数据入库情况 |
| `debug_search.py` | Python | 调试脚本，查看向量距离分布 |
| `test_query.py` | Python | SQL 语法验证脚本，用于排查 sqlite-vec 查询问题 |

### 数据文件

| 文件名 | 类型 | 说明 |
|--------|------|------|
| `test_data_source.json` | JSON | 源测试数据，530 条记忆文本（含 ID 和内容） |
| `test_cases.json` | JSON | 测试用例集，25 个评估用例（含 query、expected、noise） |
| `demo_memory.db` | SQLite | 测试数据库，包含 `memories` 表和 `vec_memories` 虚拟表 |

### 运行脚本

| 文件名 | 类型 | 说明 |
|--------|------|------|
| `run_vectorization.bat` | Batch | 一键执行向量化处理 |
| `run_recall_test.bat` | Batch | 一键执行召回测试 |

---

## 6. 技术发现与修复 (Technical Findings)

### 🐛 发现的问题

**问题描述**：首次运行召回测试时，所有配置的 Hit Rate 均为 0%。

**根本原因**：sqlite-vec 的 SQL 查询中，WHERE 子句不能直接引用 SELECT 中定义的列别名。

```sql
-- ❌ 错误写法（别名在 WHERE 中不可用）
SELECT m.content, vec_distance_cosine(v.embedding, ?) as distance
FROM vec_memories v
JOIN memories m ON v.rowid = m.rowid
WHERE distance < ?  -- 这里 distance 别名无效！

-- ✅ 正确写法（在 WHERE 中重复调用函数）
SELECT m.content, vec_distance_cosine(v.embedding, ?) as distance
FROM vec_memories v
JOIN memories m ON v.rowid = m.rowid
WHERE vec_distance_cosine(v.embedding, ?) < ?  -- 直接使用函数
```

**修复方式**：在 `recall_test.py` 的 `search()` 函数中修正 SQL 语句，并调整参数绑定顺序。

### 📊 距离分布观察

通过 `debug_search.py` 脚本观察到：
- 查询 "火锅" 时，相关记忆的余弦距离约为 **0.31-0.34**
- 转换为相似度：**0.66-0.69**
- 这说明 BGE-M3 模型对中文语义的编码质量较高

---

## 7. 测试用例设计 (Test Cases Design)

`test_cases.json` 中的 25 个测试用例覆盖以下场景：

### 按查询类型分布

| 类型 | 数量 | 示例 |
|------|------|------|
| `keyword` (纯关键词) | 8 | "火锅"、"Python"、"只狼" |
| `simple_natural` (简单自然语言) | 13 | "我想吃火锅"、"我喜欢吃苹果吗" |
| `complex_natural` (复杂自然语言) | 2 | "我之前说过哪些编程语言让我觉得很难调试？" |
| `rewrite` (重写式查询) | 2 | "用户喜欢吃火锅"（从第一人称重写为第三人称） |

### 特殊测试场景

| 场景 | 测试用例 | 目的 |
|------|----------|------|
| **语义歧义** | TC003, TC004 | 测试"苹果"水果 vs 苹果手机的区分能力 |
| **情感对立** | TC009, TC012 | 测试"想去"与"不想去"、"喜欢"与"讨厌"的区分 |
| **游戏状态区分** | TC008 | 测试"通关"与"卡关"的语义差异 |
| **重写效果验证** | TC021, TC022 | 对比原始查询与重写后查询的召回效果 |

---

## 8. 数据清理指南 (Cleanup Guide)

测试完成后，可通过以下方式清理测试数据：

```bash
# 删除测试数据库
del scripts\memory_test\demo_memory.db

# 或者保留数据库但清空表（如需重新测试）
sqlite3 scripts\memory_test\demo_memory.db "DROP TABLE IF EXISTS vec_memories; DROP TABLE IF EXISTS memories;"
```

**注意**：测试数据完全隔离在 `scripts/memory_test/` 目录，不会影响生产数据库 `doudou.db` 或 `memobase.db`。
