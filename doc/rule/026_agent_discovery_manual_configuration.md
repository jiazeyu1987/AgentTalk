# Agent发现和手动配置机制

**原则ID**: PR-026
**来源文档**: agent_discovery_manual_configuration.md
**类别**: 核心机制

---

## 原则描述

新Agent加入系统时采用手动配置机制，由管理员手动创建Agent并更新相关Agent的visibility_list，确保安全可控的Agent发现和互联。

## 设计理念

**手动配置优先于自动发现**

- 简单性：无需复杂的注册中心或自动发现机制
- 安全性：管理员明确知道谁可以看到谁
- 可控性：避免未经授权的Agent互联
- 透明性：所有visibility关系都明确定义在配置文件中

## Agent创建流程

### 1. 创建Agent文件夹结构

管理员手动创建新Agent的完整文件夹结构：

```bash
# 复制模板
cp -r template/agent_template/ system/agents/agent_xxx_new_agent/

# 配置Agent基本信息
vim system/agents/agent_xxx_new_agent/agent_profile.json
```

### 2. 定义新Agent的visibility_list

在新Agent的配置文件中定义visibility关系：

**文件位置**: `agent_xxx_new_agent/visibility_list/agent_xxx_new_agent.json`

```json
{
  "agent_id": "agent_xxx_new_agent",
  "name": "新Agent名称",
  "visibility_list": {
    "can_see": [
      "agent_general_manager",
      "agent_tech_manager"
    ],
    "can_be_seen_by": [
      "agent_general_manager",
      "agent_tech_manager"
    ]
  }
}
```

### 3. 更新GM的visibility_list

编辑GM的visibility_list，添加对新Agent的可见性：

**文件位置**: `agent_001_general_manager/visibility_list/agent_general_manager.json`

```json
{
  "agent_id": "agent_general_manager",
  "name": "总经理",
  "visibility_list": {
    "can_see": [
      "agent_002_project_manager",
      "agent_003_tech_manager",
      "agent_004_product_manager",
      "agent_xxx_new_agent"
    ],
    "can_be_seen_by": [
      "agent_002_project_manager",
      "agent_003_tech_manager",
      "agent_004_product_manager"
    ]
  }
}
```

### 4. 更新其他相关Agent

根据需要更新其他经理或相关Agent的visibility_list：

**文件位置**: `agent_003_tech_manager/visibility_list/agent_tech_manager.json`

```json
{
  "agent_id": "agent_tech_manager",
  "name": "技术经理",
  "visibility_list": {
    "can_see": [
      "agent_general_manager",
      "agent_xxx_new_agent"
    ],
    "can_be_seen_by": [
      "agent_general_manager",
      "agent_xxx_new_agent"
    ]
  }
}
```

## visibility_list配置规则

### 单向可见性

Agent A可以看到Agent B，但B看不到A：

```json
// Agent A的配置
{
  "can_see": ["agent_b"],
  "can_be_seen_by": []
}

// Agent B的配置
{
  "can_see": [],
  "can_be_seen_by": ["agent_a"]
}
```

### 双向可见性

Agent A和Agent B互相可见：

```json
// Agent A的配置
{
  "can_see": ["agent_b"],
  "can_be_seen_by": ["agent_b"]
}

// Agent B的配置
{
  "can_see": ["agent_a"],
  "can_be_seen_by": ["agent_a"]
}
```

### 层级可见性

GM看到所有经理，经理看到GM：

```json
// GM的配置
{
  "can_see": [
    "agent_project_manager",
    "agent_tech_manager",
    "agent_product_manager"
  ],
  "can_be_seen_by": [
    "agent_project_manager",
    "agent_tech_manager",
    "agent_product_manager"
  ]
}

// 项目经理的配置
{
  "can_see": ["agent_general_manager"],
  "can_be_seen_by": ["agent_general_manager"]
}
```

## Agent能力变更处理

### 能力描述更新

当Agent能力变更时，更新其visibility_list中的能力描述：

**文件位置**: `agent_xxx/visibility_list/agent_xxx.json`

```json
{
  "agent_id": "agent_backend_developer",
  "name": "后端开发者",
  "skills": [
    "Python开发",
    "API设计",
    "数据库设计",
    "容器化部署"  // 新增能力
  ],
  "inputs": [
    {"type": "text/json", "description": "API设计文档"},
    {"type": "text/json", "description": "数据库schema"}  // 新增输入
  ],
  "outputs": [
    {"type": "text/python", "description": "后端代码"},
    {"type": "text/yaml", "description": "Docker配置"}  // 新增输出
  ]
}
```

### 通知相关Agent

能力变更后，手动通知相关Agent更新其visibility_list：

1. **确定影响范围**：哪些Agent会受到影响
2. **更新visibility_list**：在受影响Agent的can_see中更新能力描述
3. **验证配置**：确保所有相关配置文件正确

## 配置验证

### 语法验证

验证JSON格式正确性：

```bash
# 验证JSON格式
cat agent_xxx/visibility_list/agent_xxx.json | jq .
```

### 一致性验证

验证visibility关系的一致性：

```python
def validate_visibility_consistency():
    """验证visibility关系是否双向一致"""

    agents = load_all_agents()

    for agent in agents:
        agent_id = agent['agent_id']
        can_see = agent['visibility_list']['can_see']
        can_be_seen_by = agent['visibility_list']['can_be_seen_by']

        # 检查can_see中的Agent是否包含当前Agent
        for target_id in can_see:
            target = find_agent(target_id)
            if agent_id not in target['visibility_list']['can_be_seen_by']:
                print(f"不一致: {agent_id}可以看到{target_id}, "
                      f"但{target_id}的can_be_seen_by中不包含{agent_id}")
```

### 可达性验证

验证GM是否可以到达所有Agent：

```python
def validate_gm_reachability():
    """验证GM是否可以到达所有Agent"""

    gm = load_agent('agent_general_manager')
    all_agents = load_all_agents()

    # BFS遍历GM可以看到的Agent
    reachable = set()
    queue = ['agent_general_manager']

    while queue:
        current = queue.pop(0)
        if current in reachable:
            continue

        reachable.add(current)
        agent = load_agent(current)

        for target_id in agent['visibility_list']['can_see']:
            if target_id not in reachable:
                queue.append(target_id)

    # 检查是否所有Agent都可到达
    for agent in all_agents:
        if agent['agent_id'] not in reachable:
            print(f"警告: {agent['agent_id']}无法从GM到达")
```

## 配置管理最佳实践

### 1. 版本控制

将所有visibility_list纳入版本控制：

```bash
# 提交visibility_list配置
git add system/agents/*/visibility_list/
git commit -m "Add new agent: agent_xxx_new_agent"
```

### 2. 配置文档

维护visibility配置文档：

**文件**: `doc/configuration/visibility_configuration.md`

```markdown
# Visibility配置记录

## Agent列表

| Agent ID | 名称 | 可见Agent | 被可见Agent |
|----------|------|-----------|-------------|
| agent_001 | 总经理 | agent_002, agent_003, agent_004 | agent_002, agent_003, agent_004 |
| agent_002 | 项目经理 | agent_001 | agent_001 |

## 配置变更历史

- 2025-01-08: 新增agent_xxx_new_agent，更新GM和Tech Manager的visibility_list
```

### 3. 配置审计

定期审计visibility配置：

```bash
# 列出所有Agent的visibility关系
for agent in system/agents/*/; do
  echo "=== $(basename $agent) ==="
  cat $agent/visibility_list/*.json | jq '.visibility_list'
  echo
done
```

### 4. 变更检查清单

新增或修改Agent时的检查清单：

- [ ] 创建Agent文件夹结构
- [ ] 配置agent_profile.json
- [ ] 定义Agent的visibility_list
- [ ] 更新GM的visibility_list
- [ ] 更新相关Agent的visibility_list
- [ ] 验证JSON格式正确性
- [ ] 验证visibility关系一致性
- [ ] 验证GM可达性
- [ ] 更新配置文档
- [ ] 提交版本控制

## 安全考虑

### 权限控制

- 只有管理员可以修改visibility_list
- Agent无法自行修改自己的visibility_list
- 防止未授权的Agent互联

### 隔离原则

- 不同团队的Agent默认不可见
- 需要显式配置才能跨团队可见
- 敏感操作的visibility需要严格审批

### 最小权限原则

- Agent只配置必需的visibility
- 不使用通配符或全可见配置
- 定期清理不再需要的visibility关系

## 错误处理

### 配置错误

**错误**: visibility_list JSON格式错误

**处理**:
1. Agent启动时验证JSON格式
2. 格式错误时拒绝启动
3. 记录错误到日志
4. 通知管理员修复

**示例**:
```python
def validate_visibility_list(agent_id):
    """验证visibility_list配置"""

    try:
        with open(f'visibility_list/{agent_id}.json') as f:
            config = json.load(f)
        # 验证必需字段
        assert 'can_see' in config['visibility_list']
        assert 'can_be_seen_by' in config['visibility_list']
        return True
    except Exception as e:
        logger.error(f"visibility_list配置错误: {e}")
        return False
```

### 一致性错误

**错误**: Agent A可以看到Agent B，但B的can_be_seen_by不包含A

**处理**:
1. 检测到不一致时记录警告
2. Agent可以继续运行
3. 通知管理员修复

## 优势和劣势

### 优势

- ✅ **简单直接**: 无需复杂的注册中心或自动发现机制
- ✅ **安全可控**: 管理员明确知道谁可以看到谁
- ✅ **透明可见**: 所有visibility关系都明确定义
- ✅ **易于调试**: 配置问题容易定位和修复
- ✅ **适合中小规模**: 对于几十到上百个Agent的系统很实用

### 劣势

- ⚠️ **人工操作**: 需要手动创建和配置
- ⚠️ **容易遗漏**: 可能忘记更新某些相关Agent
- ⚠️ **扩展性差**: 大规模系统（上千Agent）时管理困难
- ⚠️ **配置同步**: 多环境部署时需要保持配置同步

## 适用场景

### 适合

- 中小规模Agent系统（< 100个Agent）
- Agent数量增长缓慢
- Agent关系相对稳定
- 需要严格控制可见性的场景

### 不适合

- 大规模Agent系统（> 100个Agent）
- Agent频繁动态增删
- 需要完全自动化的场景
- Agent关系频繁变化

## 与其他原则的配合

### 与PR-003（安全原则）配合

- visibility_list是实现Agent文件夹隔离的关键机制
- 确保任务只会被分配给“可见”的Agent（文件系统层面的跨目录访问仍然禁止，见PR-003）

### 与PR-018（visibility_list文件格式）配合

- 遵循PR-018定义的JSON格式
- 使用标准化的agent_id、skills、inputs、outputs字段

### 与PR-009（任务分配机制）配合

- GM根据visibility_list决定任务分配给谁
- 只能分配任务给can_see中的Agent

### 与PR-025（Agent生命周期管理）配合

- 新Agent启动时验证visibility_list配置
- Agent关闭时保持visibility_list不变

## 扩展可能性

### 半自动化工具

虽然采用手动配置，但可以开发辅助工具：

```bash
# 添加新Agent的辅助脚本
python tools/add_agent.py \
  --agent-id agent_xxx_new_agent \
  --name "新Agent" \
  --can-see "agent_general_manager,agent_tech_manager" \
  --can-be-seen-by "agent_general_manager"
```

### 配置模板

提供不同类型Agent的visibility模板：

```json
// 专专家Agent模板
{
  "visibility_list": {
    "can_see": ["agent_general_manager"],
    "can_be_seen_by": ["agent_general_manager"]
  }
}

// 经理Agent模板
{
  "visibility_list": {
    "can_see": ["agent_general_manager"],
    "can_be_seen_by": ["agent_general_manager", "team_members"]
  }
}
```

## 关键要点

- **手动配置优先**: 采用手动配置而非自动发现
- **安全可控**: 管理员明确知道所有visibility关系
- **简单直接**: 无需复杂的注册中心
- **版本控制**: 所有配置纳入版本控制
- **配置验证**: 启动时验证JSON格式和一致性
- **文档记录**: 维护配置变更历史文档
- **最小权限**: 只配置必需的visibility关系
- **定期审计**: 定期检查配置的一致性和完整性

---

**最后更新**: 2025-01-08
