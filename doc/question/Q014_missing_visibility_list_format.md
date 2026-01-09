# Q014: 缺少visibility_list文件格式定义

**问题ID**: Q014
**类别**: 任务分配
**严重程度**: 🔴 严重

---

## 问题描述

PR-009提到GM有visibility_list文件夹，包含各Agent的描述（Agent ID、名字、技能、输入、输出），但没有定义文件格式。

## 场景示例

GM准备分配任务"开发电商网站"：
1. ❓ GM如何读取visibility_list下的文件？
2. ❓ 文件名应该是什么格式？agent_product_manager.md？agent_product_manager.json？
3. ❓ 文件内容应该是什么格式？Markdown？JSON？YAML？
4. ❓ "拥有的技能"如何结构化描述？

## 影响

- 无法标准化Agent能力描述
- GM无法解析Agent能力
- 任务分配无法自动化

## 关键问题

1. visibility_list下的文件命名规则是什么？
2. 文件格式是什么（JSON/YAML/Markdown）？
3. 如何描述Agent的技能、输入、输出？
4. 如何表示Agent的约束条件（如：只能处理特定类型的任务）？
5. 如何验证visibility_list文件的正确性？

## 解决方向

需要定义visibility_list文件的标准格式

---

**最后更新**: 2025-01-08
