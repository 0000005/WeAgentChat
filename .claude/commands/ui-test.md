---
allowed-tools: *
description: 执行 UI 测试
---

## Required Tools:
- ui test runner：subagent，进行 UI 集成测试
- bug fixer：subagent，修复代码中的问题

## Goals:
- 协调`ui test runner` subagent,独立运行测试用例
- 协调`bug fixer` subagent,修复未通过的测试用例
- 将最终单元测试执行结果返回给控制台

## Constrains: 
- 严格按照测试用例进行测试
- 必须严格遵循测试用例步骤，不得随意修改测试逻辑
- 每个单元测试需在`ui test runner` subagent独立运行，不能依赖其他用例

## Workflow:
1. **解析输入**：读取用户提供的测试用例
2. **环境准备**：启动项目（如未启动）
3. **执行测试**：
    - 遍历每一个用例
    - 对于每个用例，单独调用`ui test runner` subagent 运行测试用例
    - 如果用例未通过，读取测试用例的错误日志文件，并调用`bug fixer` subagent
    - 修复完成之后，重新运行测试用例直到测试用例全部通过
6. **生成报告到控制台**：
    - 汇总测试结果（通过/失败用例数量）
    - 记录所有修复操作和最终状态

## User Input:
$ARGUMENTS