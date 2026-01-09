# Plan级文件组织

**原则ID**: PR-004
**来源文档**: file_transfer_mechanism.md
**类别**: 文件组织

---

## 原则描述

plan_id是由General Manager生成的唯一标识符，代表一个完整的用户需求或项目。所有文件按plan_id组织，支持Agent并发处理多个plan。

## Plan ID定义

- **格式**: `plan_<hash>`
- **示例**: `plan_a3f5b2c8`
- **粒度**: 一个用户需求 = 一个plan_id
- **生成者**: General Manager

## 作用

1. **文件组织**: 将所有相关文件组织在同一个plan下
2. **并发处理**: 支持Agent并发处理多个plan
3. **隔离机制**: 不同plan的文件相互隔离，避免同名冲突
4. **便于管理**: 便于按plan查找和管理文件

## 目录结构

所有Agent的inbox和outbox都按plan_id组织：

```
inbox/
├── plan_a3f5b2c8/    (Plan 1的文件)
├── plan_b4g6c9d1/    (Plan 2的文件)
└── .processed/

outbox/
├── plan_a3f5b2c8/    (Plan 1的文件)
├── plan_b4g6c9d1/    (Plan 2的文件)
└── .sent/
```

## 安全原则

所有需要在Agent间共享的文件（如DLL、配置文件）必须通过inbox/outbox系统传递。每个Agent在自己的workspace中维护副本。不存在跨Agent共享目录。

## 关键要点

- **唯一性**: 每个plan有全局唯一的plan_id
- **隔离性**: 不同plan的文件互不干扰
- **并发性**: Agent可以同时处理多个plan
- **可追溯**: 所有文件都可以追溯到对应的plan

---

**最后更新**: 2025-01-08
