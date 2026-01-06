# 用户文件提交操作指南

## 文档信息

- **文档名称**：用户文件提交操作指南
- **版本**：v1.0
- **创建日期**：2025-01-06
- **目的**：详细说明用户如何将准备好的文件提交给Agent系统

---

## 一、场景说明

### 1.1 典型场景

**Day 1 - 会议结束**：
```
会议完成
  ↓
生成输入需求清单：user_inputs/meeting_001/REQUIRED_INPUTS.md
  ↓
任务分配给专家，但因缺输入处于BLOCKED状态
  ↓
系统提示："请提供以下文件：alipay_credentials.json"
```

**Day 2 - 用户准备就绪**：
```
用户终于拿到了支付宝凭据
  ↓
问题：如何把文件给Agent？
```

---

## 二、文件提交流程

### 2.1 操作步骤

**Step 1：找到放置目录**

会议结束后，系统会创建一个专门的目录：
```
user_inputs/meeting_001/
```

目录结构：
```
user_inputs/
└── meeting_001/
    ├── REQUIRED_INPUTS.md          # 系统生成的需求清单
    ├── submission_status.json      # 系统维护的提交状态
    └── [用户在这里放文件]
```

**Step 2：查看需求清单**

打开 `user_inputs/meeting_001/REQUIRED_INPUTS.md`，查看需要提供什么文件：

```markdown
# 🎯 项目输入材料需求清单

## 🔴 必须提供

### 1. alipay_credentials（支付宝凭据）

**期望格式**：JSON文件
**文件名建议**：alipay_credentials.json
**包含内容**：
- appId
- privateKey
- alipayPublicKey

**示例格式**：
```json
{
  "appId": "2021001234567890",
  "privateKey": "MIIEvQIBADANBgkqhkiG9w...",
  "alipayPublicKey": "MIIBIjANBgkqhkiG9w..."
}
```

**放置位置**：user_inputs/meeting_001/alipay_credentials.json

---

### 2. alipay_api_doc（支付宝API文档）

**期望格式**：PDF或Markdown
**文件名建议**：alipay_api_doc.pdf 或 alipay_api_doc.md
**包含内容**：
- API endpoint URL
- 签名方法
- 请求参数说明

**放置位置**：user_inputs/meeting_001/alipay_api_doc.pdf
```

**Step 3：准备文件**

按照需求清单的说明准备文件：

```bash
# 示例：用户准备支付宝凭据文件
cat > ~/alipay_credentials.json <<EOF
{
  "appId": "2021001234567890",
  "privateKey": "MIIEvQIBADANBgkqhkiG9w0BAQEFAASCBKwggSjAgEAAoIBAQC...",
  "alipayPublicKey": "MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEA..."
}
EOF

# 示例：用户从支付宝开放平台下载的API文档
# 假设文件在 ~/Downloads/alipay_api_doc.pdf
```

**Step 4：复制到指定目录**

```bash
# 将文件复制到 user_inputs/meeting_001/
cp ~/alipay_credentials.json user_inputs/meeting_001/
cp ~/Downloads/alipay_api_doc.pdf user_inputs/meeting_001/
```

**Step 5：确认文件已放置**

```bash
# 查看目录内容
ls -lh user_inputs/meeting_001/

# 输出：
# total 100
# -rw-r--r-- 1 user user  500 Jan  6 10:30 alipay_credentials.json
# -rw-r--r-- 1 user user  50K Jan  6 10:30 alipay_api_doc.pdf
# -rw-r--r-- 1 user user  2K Jan  6 09:00 REQUIRED_INPUTS.md
# -rw-r--r-- 1 user user  200 Jan  6 09:00 submission_status.json
```

**Step 6：等待系统处理**

文件监控系统会自动：
1. 检测到新文件（10秒内）
2. 通知总经理Agent
3. 总经理验证文件
4. 验证通过后，分发给对应的专家
5. 专家收到文件，解除BLOCKED状态，开始执行

---

### 2.2 系统响应时间

**时间线**：

```
T+0秒   用户放置文件到 user_inputs/meeting_001/
T+10秒  文件监控系统检测到新文件
T+20秒  总经理收到通知，开始验证
T+30秒  总经理验证完成
T+40秒  总经理分发文件给专家
T+50秒  专家收到文件，解除BLOCKED状态
T+60秒  专家开始执行任务
```

**总计**：约1分钟内，系统开始处理

---

## 三、验证与反馈

### 3.1 如何知道文件已被接收？

**方式1：查看 submission_status.json**

```bash
cat user_inputs/meeting_001/submission_status.json
```

**提交前**：
```json
{
  "meeting_id": "meeting_001",
  "last_updated": "2025-01-06T09:00:00Z",
  "status": "WAITING_FOR_INPUTS",
  "inputs": {
    "alipay_credentials": {
      "status": "NOT_RECEIVED",
      "submitted_at": null,
      "validated": false
    },
    "alipay_api_doc": {
      "status": "NOT_RECEIVED",
      "submitted_at": null,
      "validated": false
    }
  }
}
```

**提交后（1分钟内）**：
```json
{
  "meeting_id": "meeting_001",
  "last_updated": "2025-01-06T10:31:00Z",
  "status": "PROCESSING",
  "inputs": {
    "alipay_credentials": {
      "status": "RECEIVED",
      "submitted_at": "2025-01-06T10:30:15Z",
      "validated": true,
      "validation_result": "VALID"
    },
    "alipay_api_doc": {
      "status": "RECEIVED",
      "submitted_at": "2025-01-06T10:30:20Z",
      "validated": true,
      "validation_result": "VALID"
    }
  },
  "next_actions": [
    "正在分发文件给对应专家",
    "预计10秒内开始执行任务"
  ]
}
```

**方式2：查看生成的 validation_report.md**

系统会生成 `user_inputs/meeting_001/validation_report.md`：

```markdown
# 文件验证报告

**生成时间**：2025-01-06 10:30:30

---

## ✅ 验证通过

### 1. alipay_credentials.json

- **状态**：✅ VALID
- **提交时间**：2025-01-06 10:30:15
- **验证结果**：
  - ✅ 文件格式正确（JSON）
  - ✅ 包含appId字段
  - ✅ 包含privateKey字段
  - ✅ 包含alipayPublicKey字段

---

### 2. alipay_api_doc.pdf

- **状态**：✅ VALID
- **提交时间**：2025-01-06 10:30:20
- **验证结果**：
  - ✅ 文件格式正确（PDF）
  - ✅ 包含API endpoint URL
  - ✅ 包含签名方法说明
  - ✅ 包含请求参数说明

---

## 下一步

文件已分发给对应专家：
- ✅ 支付集成专家（agent_308）已收到 alipay_credentials.json
- ✅ 支付集成专家（agent_308）已收到 alipay_api_doc.pdf

预计10秒内开始执行任务：task_005（支付功能集成）
```

**方式3：查看 Dashboard（如果有）**

如果有可视化仪表板：
```
任务状态视图：
task_005: 支付功能集成
  状态：⏳ BLOCKED_WAITING_INPUT → 🟢 EXECUTING
  开始时间：2025-01-06 10:31:00
  输入文件：alipay_credentials.json, alipay_api_doc.pdf ✅
```

---

### 3.2 如果验证失败？

**示例：文件格式错误**

```bash
# 用户错误地提交了文本文件而不是JSON
cat > user_inputs/meeting_001/alipay_credentials.txt <<EOF
我的支付宝凭据是：
appId: 2021001234567890
privateKey: xxx
EOF
```

**系统响应**：

`validation_report.md`：
```markdown
# 文件验证报告

**生成时间**：2025-01-06 10:30:30

---

## ❌ 验证失败

### 1. alipay_credentials.txt

- **状态**：❌ INVALID
- **提交时间**：2025-01-06 10:30:15
- **问题**：
  - ❌ 文件格式错误（期望JSON，实际是TXT）
  - ❌ 无法解析JSON内容

---

## 如何修正

### 方式1：修正文件内容

请提供正确的JSON格式：

```json
{
  "appId": "2021001234567890",
  "privateKey": "完整的私钥内容",
  "alipayPublicKey": "完整的公钥内容"
}
```

### 方式2：重新提交

1. 删除错误文件：
   ```bash
   rm user_inputs/meeting_001/alipay_credentials.txt
   ```

2. 创建正确格式的文件：
   ```bash
   cat > user_inputs/meeting_001/alipay_credentials.json <<EOF
   {
     "appId": "2021001234567890",
     "privateKey": "...",
     "alipayPublicKey": "..."
   }
   EOF
   ```

系统会在1分钟内重新验证。

---

## 当前状态

⏳ 任务task_005仍然处于BLOCKED状态，等待正确的输入文件。
```

---

## 四、高级操作

### 4.1 分批提交文件

**场景**：第一天提交部分文件，第二天再提交剩余文件

**Day 1**：
```bash
# 先提交已准备好的文件
cp alipay_credentials.json user_inputs/meeting_001/
```

**系统响应**：
```
✅ 收到：alipay_credentials.json
⏳ 仍需：alipay_api_doc.pdf
→ 部分任务可以开始（如：准备集成代码框架）
→ 支付集成任务仍等待API文档
```

**Day 2**：
```bash
# 提交剩余文件
cp alipay_api_doc.pdf user_inputs/meeting_001/
```

**系统响应**：
```
✅ 收到：alipay_api_doc.pdf
✅ 所有必须文件已齐全
→ 支付集成任务完整启动
```

---

### 4.2 更新已提交的文件

**场景**：提交后发现文件有错误，需要修正

**方式1：直接覆盖文件**

```bash
# 直接覆盖原文件
cat > user_inputs/meeting_001/alipay_credentials.json <<EOF
{
  "appId": "2021001234567890",  // 修正后的appId
  "privateKey": "修正后的私钥",
  "alipayPublicKey": "修正后的公钥"
}
EOF
```

**系统响应**：
```
检测到文件更新：alipay_credentials.json
→ 重新验证
→ 如果验证通过，重新分发
→ 专家会使用最新的文件
```

**方式2：删除后重新提交**

```bash
# 删除旧文件
rm user_inputs/meeting_001/alipay_credentials.json

# 提交新文件（文件名可以加版本号）
cp alipay_credentials_v2.json user_inputs/meeting_001/alipay_credentials.json
```

---

### 4.3 提交时附加说明

**场景**：文件需要额外的解释说明

**创建说明文件**：

```bash
cat > user_inputs/meeting_001/alipay_credentials_README.md <<EOF
# 支付宝凭据说明

## appId
2021001234567890

## 注意事项
- 这是沙箱环境的appId（用于测试）
- 生产环境的appId稍后提供

## privateKey
使用RSA2签名方式

## 测试账号
- 买家账号：test@example.com
- 密码：123456
EOF
```

**系统会**：
- 识别 `_README.md` 或 `_NOTE.md` 后缀的文件
- 将其作为附加说明，随主文件一起发送给专家
- 专家会参考说明内容

---

### 4.4 无法提供某些文件

**场景**：确实无法提供某个必须的文件

**创建说明文件**：

```bash
cat > user_inputs/meeting_001/alipay_credentials_NOT_AVAILABLE.md <<EOF
# 支付宝凭据暂时无法提供

## 原因
支付宝企业账号正在申请中，预计3天后获批。

## 建议
1. 是否可以先使用沙箱环境进行开发？
2. 或者先开发其他不依赖支付的功能？

## 替代方案
如果可以使用沙箱环境，凭据如下：
- appId: 2021000000000000（沙箱）
- ...
EOF
```

**系统会**：
- 将此说明通知总经理
- 总经理组织专家会议讨论替代方案
- 可能的决策：
  - 使用沙箱环境
  - 调整任务优先级
  - 先开发其他功能

---

## 五、文件监控机制

### 5.1 系统如何检测新文件？

**方式1：轮询（MVP阶段）**

```python
# 文件监控服务（每10秒检查一次）
class UserInputMonitor:
    def run(self):
        while True:
            # 扫描 user_inputs/meeting_001/
            for file in os.listdir("user_inputs/meeting_001/"):
                if self.is_new_file(file):
                    self.notify_general_manager(file)

            sleep(10)
```

**方式2：文件系统事件（优化阶段）**

```python
# 使用 inotify（Linux）或 FSEvents（macOS）
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

class InputFileHandler(FileSystemEventHandler):
    def on_created(self, event):
        if not event.is_directory:
            self.notify_general_manager(event.src_path)

    def on_modified(self, event):
        # 文件被修改时也触发
        if not event.is_directory:
            self.notify_general_manager(event.src_path)
```

### 5.2 检测延迟

| 监控方式 | 检测延迟 | 资源占用 |
|---------|---------|---------|
| 轮询（10秒） | 0-10秒 | 低 |
| 文件系统事件 | <1秒 | 极低 |

**推荐**：
- MVP阶段：使用轮询（简单可靠）
- 生产环境：使用文件系统事件（更高效）

---

## 六、实际操作演示

### 6.1 完整操作流程（以电商网站为例）

**背景**：
- 会议ID：meeting_001
- 任务：开发支付功能
- 需要：alipay_credentials.json, alipay_api_doc.pdf
- 用户需要1天时间准备材料

**Day 1（会议当天）**：

```bash
# 1. 会议结束，查看需求清单
cat user_inputs/meeting_001/REQUIRED_INPUTS.md

# 输出：
# 需要提供：
# 1. alipay_credentials.json
# 2. alipay_api_doc.pdf

# 2. 目录结构确认
ls -lh user_inputs/meeting_001/
# -rw-r--r-- 1 user user 2K Jan 6 09:00 REQUIRED_INPUTS.md
# -rw-r--r-- 1 user user 200 Jan 6 09:00 submission_status.json

# 3. 查看状态
cat user_inputs/meeting_001/submission_status.json
# "status": "WAITING_FOR_INPUTS"
```

**Day 2（文件准备就绪）**：

```bash
# 4. 用户准备好了文件
ls -lh ~/alipay_*
# -rw-r--r-- 1 user user 500 Jan 7 10:00 alipay_credentials.json
# -rw-r--r-- 1 user user 50K Jan 7 10:00 alipay_api_doc.pdf

# 5. 复制到指定目录
cp ~/alipay_credentials.json user_inputs/meeting_001/
cp ~/alipay_api_doc.pdf user_inputs/meeting_001/

# 6. 确认文件已放置
ls -lh user_inputs/meeting_001/
# -rw-r--r-- 1 user user  500 Jan 7 10:01 alipay_credentials.json  ✅ 新
# -rw-r--r-- 1 user user 50K Jan 7 10:01 alipay_api_doc.pdf      ✅ 新
# -rw-r--r-- 1 user user  2K Jan 6 09:00 REQUIRED_INPUTS.md
# -rw-r--r-- 1 user user  200 Jan 6 09:00 submission_status.json

# 7. 等待系统处理（约1分钟）
sleep 60

# 8. 查看更新后的状态
cat user_inputs/meeting_001/submission_status.json

# 输出：
# {
#   "status": "PROCESSING",
#   "inputs": {
#     "alipay_credentials": {
#       "status": "RECEIVED",
#       "validated": true
#     },
#     "alipay_api_doc": {
#       "status": "RECEIVED",
#       "validated": true
#     }
#   },
#   "next_actions": [
#     "文件已分发给支付集成专家",
#     "专家已开始执行任务"
#   ]
# }

# 9. 查看验证报告
cat user_inputs/meeting_001/validation_report.md

# 输出：
# # 文件验证报告
#
# ## ✅ 验证通过
#
# ### 1. alipay_credentials.json
# - 状态：✅ VALID
#
# ### 2. alipay_api_doc.pdf
# - 状态：✅ VALID
#
# ## 下一步
# 文件已分发，专家已开始执行任务
```

**Day 2+（专家执行中）**：

```bash
# 10. 用户可以随时查看进度
# （如果有Dashboard，打开Web界面查看）
# 或者查看日志
tail -f logs/agent_activity.jsonl | grep "task_005"

# 输出：
# {"timestamp": "2025-01-07T10:05:00Z", "agent": "agent_308", "task": "task_005", "status": "EXECUTING", "message": "开始分析支付宝API文档"}
# {"timestamp": "2025-01-07T10:15:00Z", "agent": "agent_308", "task": "task_005", "status": "EXECUTING", "message": "编写支付接口代码"}
# {"timestamp": "2025-01-07T11:30:00Z", "agent": "agent_308", "task": "task_005", "status": "READY_TO_CHECK", "message": "支付功能开发完成，待审查"}
```

---

## 七、常见问题

### Q1：我可以把文件放到其他目录吗？

**A**：不建议。系统只监控 `user_inputs/meeting_001/` 目录。

如果确实需要使用其他位置：
1. 创建软链接：
   ```bash
   ln -s ~/my_files/alipay_credentials.json user_inputs/meeting_001/
   ```
2. 或者复制到指定目录（推荐）

---

### Q2：文件名必须严格按照建议吗？

**A**：建议按照建议命名，但系统也会通过内容识别。

**优先级**：
1. 精确匹配：`alipay_credentials.json` ✅ 最准确
2. 关键词匹配：`支付宝凭据.json` ✅ 可以识别
3. 后缀匹配：`credentials.json` ⚠️ 可能有歧义

**建议**：按照需求清单中的建议命名，避免歧义。

---

### Q3：提交后多久能开始处理？

**A**：
- **检测时间**：<10秒（轮询）或 <1秒（文件系统事件）
- **验证时间**：10-30秒
- **分发时间**：10秒
- **总计**：约1分钟内开始处理

---

### Q4：我可以提交ZIP压缩包吗？

**A**：可以。

```bash
# 打包多个文件
zip -j payment_files.zip alipay_credentials.json alipay_api_doc.pdf

# 提交ZIP文件
cp payment_files.zip user_inputs/meeting_001/
```

**系统会自动**：
1. 检测到ZIP文件
2. 解压到临时目录
3. 验证解压后的文件
4. 分发给对应专家

---

### Q5：如果我在Agent执行过程中更新了文件？

**A**：
1. 文件监控系统会检测到文件修改
2. 总经理会重新验证文件
3. 如果验证通过，通知专家更新输入
4. 专家会根据最新输入调整执行

**注意**：如果专家已经完成了部分工作，可能需要重新做。

**建议**：
- 尽量在专家开始执行前提交正确的文件
- 如果必须更新，尽早更新
- 可以在文件名中标注版本（如：alipay_credentials_v2.json）

---

### Q6：我怎么知道专家已经收到文件？

**A**：查看 `submission_status.json` 或 `validation_report.md`

**示例**：
```json
{
  "inputs": {
    "alipay_credentials": {
      "status": "RECEIVED_AND_DELIVERED",
      "validated": true,
      "delivered_to": "agent_308_payment_expert",
      "delivered_at": "2025-01-07T10:31:00Z"
    }
  }
}
```

---

## 八、总结

### 提交流程（简化版）

```
1. 查看 user_inputs/meeting_001/REQUIRED_INPUTS.md
   ↓
2. 按要求准备文件
   ↓
3. 复制文件到 user_inputs/meeting_001/
   ↓
4. 等待1分钟
   ↓
5. 查看 submission_status.json 或 validation_report.md
   ↓
6. 确认专家已收到并开始执行
```

### 关键点

- ✅ **放置位置**：`user_inputs/meeting_001/`
- ✅ **响应时间**：约1分钟
- ✅ **验证反馈**：自动生成 `validation_report.md`
- ✅ **状态查询**：查看 `submission_status.json`
- ✅ **分批提交**：支持多次提交
- ✅ **文件更新**：支持覆盖和更新

### 用户体验

> **"像把文件放到共享文件夹一样简单"**
>
> - 不需要登录系统
> - 不需要使用特殊命令
> - 不需要知道哪个Agent需要
> - 只需要把文件放到指定目录
> - 系统自动处理其他一切

---

**文档版本**：v1.0
**创建日期**：2025-01-06
**状态**：✅ 用户文件提交操作指南完成
