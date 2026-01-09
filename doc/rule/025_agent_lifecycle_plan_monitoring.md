# Agent生命周期管理和Plan监控机制

**原则ID**: PR-025
**来源文档**: agent_lifecycle_plan_monitoring.md
**类别**: 核心机制

---

## 原则描述

每个Agent有标准的启动、关闭、重启脚本。监控程序监控agent_status/目录，可以手动重启异常Agent。GM Agent在Plan开始时写入agent_list.json，监控系统可以查看Plan中哪些Agent未启动。

## Agent目录结构

### 批处理脚本

每个Agent文件夹下包含三个批处理脚本：

```
agent_xxx_name/
├── start.bat      # 启动Agent
├── stop.bat       # 关闭Agent（关闭心跳程序）
└── restart.bat    # 重启Agent
```

## 启动脚本 (start.bat)

### 功能

启动Agent的心跳程序。

### 单例启动机制

**防止重复启动**:
1. 检查心跳程序是否已经运行
2. 如果已运行，显示提示信息并退出
3. 如果未运行，启动心跳程序

### 实现逻辑

```batch
@echo off
REM Agent启动脚本

echo Checking if Agent is already running...

REM 检查心跳进程是否存在
tasklist /FI "IMAGENAME eq python.exe" /FI "WINDOWTITLE eq *agent_xxx_name*" | find /I "python.exe" >nul

if %ERRORLEVEL% EQU 0 (
    echo Agent is already running!
    echo To restart the Agent, please use restart.bat
    pause
    exit /b 0
)

echo Starting Agent...
cd /d "%~dp0"

REM 启动心跳程序
start "Agent: agent_xxx_name" python core/main.py

echo Agent started successfully!
pause
```

### 关键要点

- **检查现有进程**: 通过tasklist查找python.exe进程
- **进程标识**: 使用WINDOWTITLE区分不同Agent
- **提示信息**: 已运行时给出明确提示
- **返回值**: 成功返回0，失败返回非0

## 关闭脚本 (stop.bat)

### 功能

关闭Agent的心跳程序。

### 实现逻辑

```batch
@echo off
REM Agent关闭脚本

echo Stopping Agent: agent_xxx_name...

REM 查找并终止心跳进程
for /f "tokens=2" %%a in ('tasklist /FI "IMAGENAME eq python.exe" /FI "WINDOWTITLE eq *agent_xxx_name*" ^| find /I "python.exe" ^| find /I "agent_xxx_name*"') do (
    echo Terminating process %%a...
    taskkill /PID %%a /F
)

echo Agent stopped!
pause
```

### 关键要点

- **精确匹配**: 通过WINDOWTITLE精确匹配Agent
- **强制终止**: 使用/F参数强制终止
- **清理**: 确保进程完全终止
- **提示**: 显示停止状态

## 重启脚本 (restart.bat)

### 功能

重启Agent的心跳程序。

### 实现逻辑

```batch
@echo off
REM Agent重启脚本

echo Restarting Agent: agent_xxx_name...

REM 先关闭
call stop.bat

REM 等待进程完全终止
timeout /t 2 /nobreak >nul

REM 再启动
call start.bat

echo Agent restarted!
```

### 关键要点

- **先停后启**: 先调用stop.bat，再调用start.bat
- **等待间隔**: 等待2秒确保进程完全终止
- **重用脚本**: 复用start.bat和stop.bat
- **状态反馈**: 显示重启状态

## GM Agent写入agent_list.json

### 写入时机

GM Agent在Plan开始时写入agent_list.json。

### 文件位置

```
shared_folder_path/plan_id/agent_list.json
```

### 文件格式

```json
{
  "plan_id": "plan_develop_ecommerce",
  "plan_name": "开发电商网站",
  "created_at": "2025-01-08T10:00:00Z",
  "agents": [
    {
      "agent_id": "agent_001_product_manager",
      "agent_name": "产品经理",
      "required": true,
      "status": "EXPECTED",
      "expected_start_time": "2025-01-08T10:00:00Z"
    },
    {
      "agent_id": "agent_002_database_expert",
      "agent_name": "数据库专家",
      "required": true,
      "status": "EXPECTED",
      "expected_start_time": "2025-01-08T10:00:00Z"
    },
    {
      "agent_id": "agent_003_backend_developer",
      "agent_name": "后端开发者",
      "required": true,
      "status": "EXPECTED",
      "expected_start_time": "2025-01-08T10:05:00Z"
    }
  ]
}
```

### 字段说明

#### plan_id

Plan的唯一标识符。

#### plan_name

Plan的可读名称。

#### created_at

Plan创建时间。

#### agents

参与此Plan的Agent列表。

**每个Agent包含**:
- **agent_id**: Agent唯一标识符
- **agent_name**: Agent可读名称
- **required**: 是否必需（true/false）
- **status**: 状态
  - `EXPECTED`: 预期启动
  - `RUNNING`: 运行中
  - `STOPPED`: 已停止
- **expected_start_time**: 预期启动时间

## 监控程序

### 监控对象

监控程序监控两个文件：

1. **agent_list.json**: 查看Plan中哪些Agent应该启动
2. **agent_status/**: 查看哪些Agent实际运行

### 监控逻辑

```python
def monitor_plan(plan_id):
    # 读取agent_list.json
    agent_list_file = os.path.join(shared_folder_path, plan_id, "agent_list.json")

    with open(agent_list_file) as f:
        agent_list = json.load(f)

    # 检查每个Agent的状态
    for agent_info in agent_list['agents']:
        agent_id = agent_info['agent_id']
        required = agent_info['required']

        # 读取Agent状态
        status_file = os.path.join(shared_folder_path, "agent_status", f"agent_{agent_id}.json")

        if not os.path.exists(status_file):
            # 状态文件不存在，Agent未启动
            if required:
                alert(f"必需Agent未启动: {agent_id}")
            continue

        with open(status_file) as f:
            status = json.load(f)

        # 检查心跳是否超时
        last_heartbeat = datetime.fromisoformat(status['last_heartbeat'])
        now = datetime.now()

        if (now - last_heartbeat).total_seconds() > heartbeat_timeout:
            alert(f"Agent心跳超时: {agent_id}")
```

### 监控告警

**告警类型**:

1. **必需Agent未启动**
   - 状态文件不存在
   - Agent未在agent_list中
   - 需要手动启动

2. **Agent心跳超时**
   - last_heartbeat超时
   - Agent可能异常或崩溃
   - 可以手动重启

3. **Agent状态异常**
   - health != "HEALTHY"
   - 有last_error
   - 需要人工介入

## 手动重启机制

### 重启场景

当监控发现Agent异常时，可以手动重启。

### 手动重启流程

1. **定位Agent**
   - 通过agent_status找到异常Agent
   - 确定Agent文件夹路径

2. **执行重启**
   ```batch
   cd agent_xxx_name/
   restart.bat
   ```

3. **验证重启**
   - 检查agent_status/agent_xxx.json是否更新
   - 确认last_heartbeat是最近的

### 重启脚本增强

支持远程重启：

```batch
@echo off
REM 手动重启Agent脚本（支持远程调用）

if "%1"=="" (
    echo Usage: manual_restart.bat [agent_folder_path]
    echo Example: manual_restart.bat D:\AgentTalk\agents\agent_001
    pause
    exit /b 1
)

set AGENT_PATH=%1

echo Manually restarting Agent at: %AGENT_PATH%

cd /d "%AGENT_PATH%"
call restart.bat

echo Manual restart completed!
```

## Plan关闭机制

### 关闭流程

当需要关闭一个Plan时：

1. **停止所有Agent**
   - 读取agent_list.json获取所有Agent
   - 依次调用每个Agent的stop.bat
   - 等待所有Agent完全停止

2. **清理inbox和outbox**
   - 删除inbox/plan_id/下所有内容
   - 删除outbox/plan_id/下所有内容
   - 保留其他plan的文件

3. **可选：清理其他文件**
   - 清理workspace/plan_xxx/
   - 清理shared_folder_path/plan_id/
   - 根据需求决定是否保留

### 关闭脚本

```batch
@echo off
REM Plan关闭脚本

set PLAN_ID=%1

if "%PLAN_ID%"=="" (
    echo Usage: close_plan.bat [plan_id]
    pause
    exit /b 1
)

echo Closing Plan: %PLAN_ID%

REM 读取agent_list.json
set AGENT_LIST_FILE=shared_folder_path\%PLAN_ID%\agent_list.json

if not exist %AGENT_LIST_FILE% (
    echo Error: agent_list.json not found for plan %PLAN_ID%
    pause
    exit /b 1
)

REM 解析agent_list.json并停止每个Agent
REM 使用Python脚本来解析JSON
python -c "import json; agents = json.load(open('%AGENT_LIST_FILE%')); [print(a['agent_id']) for a in agents['agents']]" > temp_agents.txt

for /f %%a in (temp_agents.txt) do (
    echo Stopping Agent: %%a
    cd agents\%%a
    call stop.bat
)

del temp_agents.txt

REM 清理inbox和outbox
echo Cleaning inbox/%PLAN_ID%/...
rd /s /q inbox\%PLAN_ID%

echo Cleaning outbox/%PLAN_ID%/...
rd /s /q outbox\%PLAN_ID%

echo Plan %PLAN_ID% closed successfully!
pause
```

### 清理验证

清理前验证：

1. **确认Plan ID正确**
2. **确认所有Agent已停止**
3. **备份重要数据**（可选）

## 关键要点

- **批处理脚本**: 每个Agent有start.bat、stop.bat、restart.bat
- **单例启动**: 多次点击启动不重复启动
- **进程管理**: 通过WINDOWTITLE区分不同Agent进程
- **GM写agent_list**: Plan开始时写入agent_list.json
- **监控程序**: 监控agent_list和agent_status
- **手动重启**: 发现异常时可以手动重启
- **Plan关闭**: 停止所有Agent，清理inbox和outbox
- **Plan隔离**: 通过plan_id组织，防止互相干扰

## 与其他原则的配合

### 与PR-024（公用文件夹和状态监控）配合

- agent_list.json写入shared_folder/plan_id/
- Agent状态写入shared_folder/agent_status/
- 监控程序读取这两个位置

### 与PR-011（统一轮询工作方式）配合

- 启动脚本启动心跳程序
- 心跳程序实现轮询机制
- 关闭脚本停止心跳程序

### 与PR-017（日志追踪）配合

- 启动、关闭、重启操作记录到日志
- 监控告警记录到日志

## 安全考虑

### 权限控制

- 启动脚本：任何用户可以启动
- 关闭脚本：任何用户可以关闭
- 监控程序：只读权限，不修改Agent状态
- 手动重启：需要管理员权限

### 清理验证

清理inbox/outbox前验证：
- 确认所有Agent已停止
- 确认没有正在进行的任务
- 确认重要数据已备份

---

**最后更新**: 2025-01-08
