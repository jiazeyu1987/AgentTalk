# 安全原则：每个Agent只能访问自己的文件夹

**原则ID**: PR-003
**来源文档**: file_transfer_mechanism.md
**类别**: 安全机制

---

## 原则描述

每个Agent只能操作自己的文件夹，不能访问其他Agent的文件夹。

## 文件组织结构

- 每个Agent的inbox: `agents/<agent_id>/inbox/`
- 每个Agent的outbox: `agents/<agent_id>/outbox/`
- 每个Agent的workspace: `agents/<agent_id>/workspace/`
- 每个Agent只能读写自己目录下的文件

## 访问限制

Agent不能访问其他Agent的文件夹，包括：
- 不能读取其他Agent的 `workspace/`
- 不能读取其他Agent的 `inbox/`
- 不能写入其他Agent的任何目录

## 文件共享机制

所有文件共享都通过 inbox/outbox 系统实现：

1. 文件从Agent A的 `outbox/<plan_id>/` 出来
2. 系统投递到Agent B的 `inbox/<plan_id>/`
3. Agent B从自己的 `inbox/<plan_id>/` 读取文件副本
4. 整个过程不需要跨目录访问

## 关键要点

- **安全隔离**: Agent之间完全隔离，避免相互干扰
- **权限控制**: 每个Agent只能访问自己的文件系统
- **副本机制**: 接收方获得的是文件副本，不影响原始文件
- **系统中介**: 所有跨Agent的文件传递都由系统完成

---

**最后更新**: 2025-01-08
