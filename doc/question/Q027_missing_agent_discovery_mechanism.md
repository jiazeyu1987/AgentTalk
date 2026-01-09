# Q027: 缺少Agent发现机制

**问题ID**: Q027
**类别**: 发现
**严重程度**: 🟢 低

**状态**: ✅ 已解决 - 手动配置机制

---

## 问题描述

新Agent加入系统时，没有机制让其他Agent（特别是GM）发现并更新visibility_list。

## 场景示例

1. 新增一个"Security Expert" Agent
2. ❌ GM如何知道这个新Agent？
3. ❌ 如何更新GM的visibility_list？
4. ❌ 是否需要人工配置？
5. ❌ Agent能力变更后如何通知？

## 影响

- 新Agent无法被发现
- GM无法分配任务给新Agent
- 需要手动配置，容易出错

## 解决方案

✅ **采用手动配置机制**

**设计决策**:
- 新Agent加入时，手动决定谁能看到他
- 手动更新经理（GM）的visibility_list
- 这是一个有意为之的设计，而非自动化机制

**实现方式**:

1. **创建新Agent时**:
   - 管理员手动创建Agent文件夹
   - 在新Agent的agent_profile.json中定义visibility_list
   - 决定哪些Agent可以看到这个新Agent

2. **更新GM的visibility_list**:
   - 编辑GM的visibility_list/agent_xxx.json
   - 添加新Agent的描述到can_see列表
   - 更新can_be_seen_by列表

3. **更新其他相关Agent**:
   - 如果需要，更新其他经理Agent的visibility_list
   - 确保visibility关系双向正确

**优势**:
- ✅ 简单直接，无需复杂的注册中心
- ✅ 安全可控，管理员明确知道谁可以看到谁
- ✅ 避免自动发现可能带来的安全问题
- ✅ 适合中小规模Agent系统

**劣势**:
- ⚠️ 需要人工操作
- ⚠️ 大规模系统时可能繁琐
- ⚠️ 容易遗漏更新相关Agent

## 关键问题

1. ~~新Agent如何注册到系统？~~ ✅ 手动创建和配置
2. ~~GM如何发现新Agent？~~ ✅ 手动更新visibility_list
3. ~~Agent能力变更如何通知？~~ ✅ 手动更新相关Agent的visibility_list
4. ~~是否需要Agent注册中心？~~ ✅ 不需要，采用手动配置
5. ~~如何验证Agent身份？~~ ✅ 通过agent_id和文件夹路径验证

## 相关文档

- [PR-018: visibility_list文件格式](../rule/018_visibility_list_format.md)
- [CLAUDE.md - Agent Visibility List](../../../CLAUDE.md)

---

**最后更新**: 2025-01-08
