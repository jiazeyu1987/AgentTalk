# 并发控制机制

**原则ID**: PR-023
**来源文档**: concurrency_control.md
**类别**: 核心机制

---

## 原则描述

同一个Agent内部不并发，串行处理任务。并发存在于多个Agent之间，通过文件传递机制实现天然的并发。

## 核心思想

**Agent内串行，Agent间并行**:
- 同一个Agent同时只处理一个任务
- 多个Agent可以同时处理不同的任务
- 通过inbox/outbox文件传递实现Agent间并发

## Agent内串行处理

### 单任务处理

Agent在任何时候最多处理一个任务：

```
Agent的生命周期：
  IDLE → 接收任务 → 处理中 → 完成 → IDLE
```

### 任务队列

Agent维护一个任务队列：

```
任务队列：
  [task_001, task_002, task_003, ...]
     ↑
  当前处理
```

**队列管理**:
- 新任务到达时加入队列尾部
- Agent从队列头部取任务处理
- 处理完一个任务后，取下一个任务
- 队列为空时，Agent进入IDLE状态

### 阻塞等待

Agent处理任务时可能需要等待输入：

**等待期间的行为**:
1. Agent将任务标记为BLOCKED
2. Agent继续处理队列中的下一个任务
3. 不创建新的线程或进程
4. 输入到达后，任务变回READY状态

**示例**:
```
任务队列初始状态：
  [task_001(READY), task_002(READY), task_003(READY)]

Agent处理task_001，等待输入：
  [task_001(BLOCKED), task_002(READY), task_003(READY)]

Agent切换到task_002：
  [task_001(BLOCKED), task_002(RUNNING), task_003(READY)]

输入到达，task_001变回READY：
  [task_001(READY), task_002(RUNNING), task_003(READY)]

Agent完成task_002，处理task_001：
  [task_001(RUNNING), task_003(READY)]
```

## Agent间并发

### 天然并发

多个Agent可以同时处理任务：

```
时间线：
  t0: GM分配任务
      task_001 → PM Agent
      task_002 → DB Expert
      task_003 → Backend Dev

  t1: 三个Agent同时处理（并发）
      PM Agent: 处理task_001
      DB Expert: 处理task_002
      Backend Dev: 处理task_003

  t2: PM Agent完成
      PM Agent: IDLE
      DB Expert: 处理中
      Backend Dev: 处理中
```

### 通过文件传递解耦

Agent之间通过inbox/outbox传递文件，天然解耦：

```
PM Agent                    Backend Dev
  |                             |
  | 生成requirements.md         |
  | → outbox/                   |
  |                             | inbox/
  |                             | ← requirements.md
  |                             | 读取并处理
```

**优势**:
- 无需锁机制
- 无需共享内存
- 无需同步原语
- 文件系统提供天然的隔离

## 并发场景

### 场景1: 并行执行独立任务

```
GM分配：
  task_001: 需求分析 → PM Agent
  task_002: 前端设计 → UI Designer
  task_003: 后端设计 → Tech Lead

三个Agent同时处理（并发）
```

### 场景2: 流水线处理

```
依赖关系：task_001 → task_002 → task_003

t0: task_001 → Agent A (处理中)
    task_002: 等待task_001
    task_003: 等待task_002

t1: task_001完成 → Agent A IDLE
    task_002 → Agent B (开始处理)
    task_003: 等待task_002

t2: task_002完成 → Agent B IDLE
    task_003 → Agent C (开始处理)

效果：流水线并发，不同阶段由不同Agent并行处理
```

### 场景3: 同一Agent串行处理多个任务

```
PM Agent收到3个任务：
  task_001: 分析需求A
  task_002: 分析需求B
  task_003: 分析需求C

PM Agent串行处理：
  t0: 处理task_001
  t1: task_001完成，处理task_002
  t2: task_002完成，处理task_003
  t3: task_003完成，PM Agent IDLE

效果：同一Agent内无并发，完全串行
```

## 状态管理

### Agent全局状态

Agent维护一个全局状态：

```
可能的状态：
  - IDLE: 空闲，可以接收新任务
  - BUSY: 正在处理任务
  - BLOCKED: 等待输入，但可以处理其他任务
```

### 任务状态

每个任务维护自己的状态：

```
可能的状态：
  - PENDING: 在队列中等待
  - READY: 输入齐全，可以执行
  - RUNNING: 正在执行
  - BLOCKED: 等待输入
  - COMPLETED: 完成
  - FAILED: 失败
```

### 状态转换

```
任务状态转换：
  PENDING → READY (输入齐全)
  READY → RUNNING (Agent开始处理)
  RUNNING → BLOCKED (等待输入)
  BLOCKED → READY (输入到达)
  RUNNING → COMPLETED (完成)
  RUNNING → FAILED (失败)
```

## 任务调度

### 调度策略

Agent使用简单的FIFO调度：

```
任务队列：
  [task_001, task_002, task_003, ...]

调度顺序：
  1. 从队列头部取任务
  2. 如果任务是READY状态，执行
  3. 如果任务是BLOCKED状态，跳过
  4. 完成后，取下一个任务
```

### 优先级处理

如果需要支持任务优先级：

```
任务队列按优先级排序：
  [task_001(HIGH), task_002(MEDIUM), task_003(LOW)]

调度策略：
  1. 优先处理HIGH优先级任务
  2. HIGH处理完后，处理MEDIUM
  3. 最后处理LOW
```

## 关键要点

- **Agent内串行**: 同一Agent同时只处理一个任务
- **Agent间并行**: 多个Agent可以同时处理不同任务
- **简单队列**: 使用FIFO队列管理任务
- **阻塞不等待**: 任务阻塞时，处理下一个任务
- **文件解耦**: 通过文件传递实现Agent间解耦
- **无需同步**: 不需要锁、信号量等同步机制
- **状态跟踪**: 维护Agent全局状态和任务状态

## 与其他原则的配合

### 与PR-001（inbox/outbox文件传递）配合

- 文件传递机制天然支持并发
- 不同Agent的inbox/outbox相互隔离

### 与PR-011（统一轮询工作方式）配合

- 轮询扫描inbox，发现新任务
- 串行处理队列中的任务

### 与PR-017（日志追踪）配合

- 记录Agent的状态变化
- 记录任务的调度和执行历史

---

**最后更新**: 2025-01-08
