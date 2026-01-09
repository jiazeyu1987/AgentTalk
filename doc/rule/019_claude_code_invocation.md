# Claude Code调用机制

**原则ID**: PR-019
**来源文档**: claude_code_integration.md
**类别**: 核心机制

---

## 原则描述

Agent通过调用本地claude code CLI来利用LLM能力。支持两种provider：claude_code（本地CLI）和anthropic API。

## 实现基础

基于`llm_communication.py`中的`SimpleLLMService`类，提供统一的LLM调用接口。

### 核心类

**SimpleLLMService**:
- 位置: `src/llm_demo/llm_communication.py`
- 提供统一的LLM调用方法
- 支持claude_code和anthropic两种provider

### 配置方式

通过`runtime_config.json`配置LLM provider：

```json
{
  "llm": {
    "provider": "claude_code",
    "claude_code_bin": "/path/to/claude",
    "timeout_s": 300
  }
}
```

## Provider选择

### claude_code Provider

**调用方式**: 通过subprocess调用本地claude code CLI

**实现**:
```python
def _claude_code_call(self, prompt: str, *, timeout_s: int = 300) -> str:
    completed = subprocess.run(
        [bin_path],
        input=prompt,
        text=True,
        capture_output=True,
        timeout=timeout_s,
        check=False,
    )
    if completed.returncode != 0:
        stderr = (completed.stderr or "").strip()
        raise RuntimeError(f"claude_code returned {completed.returncode}: {stderr}")
    return (completed.stdout or "").strip()
```

**优势**:
- 本地调用，无需API密钥
- 支持skill调用
- 支持文件读取
- 可以调用本地工具

### anthropic API Provider

**调用方式**: 通过anthropic Python SDK调用API

**实现**:
```python
import anthropic

self.client = anthropic.Anthropic(api_key=api_key)
response = self.client.messages.create(
    model=self.default_model,
    max_tokens=self.default_max_tokens,
    messages=[{"role": "user", "content": prompt}]
)
return response.content[0].text
```

**优势**:
- 标准API调用
- 稳定可靠
- 支持流式响应

## 调用方法

### 1. llm_call - 基础调用

最简单的LLM调用方法。

**签名**:
```python
def llm_call(self, prompt: str) -> str
```

**使用示例**:
```python
from llm_communication import simple_llm_service

prompt = "什么是Python？"
response = simple_llm_service.llm_call(prompt)
print(response)
```

**返回值**: 字符串，LLM的响应内容

### 2. simple_llm - 简单调用

支持自定义模型和max_tokens的调用方法。

**签名**:
```python
def simple_llm(self, prompt: str, model: str = None, max_tokens: int = None) -> str
```

**使用示例**:
```python
response = simple_llm_service.simple_llm(
    prompt="解释机器学习",
    model="claude-3-sonnet-20240229",
    max_tokens=100
)
```

### 3. llm_call_with_history - 带历史记录的调用

支持对话历史的调用方法。

**签名**:
```python
def llm_call_with_history(
    self,
    prompt: str,
    history: Optional[List[Dict[str, str]]] = None,
    model: str = None,
    max_tokens: int = None
) -> str
```

**使用示例**:
```python
history = [
    {"role": "user", "content": "你好"},
    {"role": "assistant", "content": "你好！有什么可以帮助你的吗？"}
]
response = simple_llm_service.llm_call_with_history(
    "现在的问题是：什么是人工智能？",
    history=history
)
```

### 4. generate_response - 完整响应生成

返回结构化的LLMResponse对象。

**签名**:
```python
def generate_response(
    self,
    messages: List[Dict[str, Any]],
    model: str = None,
    max_tokens: int = None,
    request_id: str = None,
    **kwargs
) -> LLMResponse
```

**LLMResponse对象**:
```python
@dataclass
class LLMResponse:
    content: str              # 响应内容
    model: str               # 使用的模型
    usage: Dict[str, int]     # token使用量
    response_time: float      # 响应时间（秒）
    provider: str             # provider标识
```

**使用示例**:
```python
messages = [
    {"role": "user", "content": "请解释Python是什么"},
    {"role": "assistant", "content": "Python是一种编程语言"},
    {"role": "user", "content": "它有什么特点？"}
]

response = simple_llm_service.generate_response(messages)
print(f"内容: {response.content}")
print(f"模型: {response.model}")
print(f"用时: {response.response_time:.2f}秒")
print(f"tokens: {response.usage}")
```

## 文件读取

### 在提示词中引用文件

Agent需要在提示词中包含文件路径，claude code会自动读取：

```
请分析以下需求文档：

文件路径: /inbox/plan_xxx/requirements.md

基于该文档生成用户故事列表。
```

### 文件内容注入

claude code读取文件后，自动注入到提示词中。

## 错误处理

### 调用失败

所有方法在调用失败时返回错误信息：

```python
response = simple_llm_service.llm_call(prompt)
if response.startswith("调用失败"):
    # 处理错误
    logger.error(f"LLM调用失败: {response}")
```

### 异常处理

```python
try:
    response = simple_llm_service.llm_call(prompt)
except Exception as e:
    logger.error(f"LLM调用异常: {str(e)}")
    # 处理异常
```

## 性能考虑

### 流式响应

`generate_response`方法使用流式响应，避免长请求超时：

```python
response = self.client.messages.create(
    model=model,
    max_tokens=40960,
    messages=anthropic_messages,
    stream=True
)
```

### 响应时间记录

所有调用都记录响应时间，便于性能分析：

```python
start_time = time.time()
# ... LLM调用 ...
response_time = time.time() - start_time
```

## 关键要点

- **双provider支持**: 支持claude_code和anthropic两种provider
- **统一接口**: 通过SimpleLLMService提供统一的调用方法
- **配置驱动**: 通过runtime_config.json配置provider
- **本地优先**: 优先使用claude_code provider
- **文件读取**: 支持在提示词中引用文件路径
- **结构化返回**: generate_response返回LLMResponse对象
- **性能记录**: 所有调用记录响应时间和token使用量
- **错误处理**: 统一的错误处理和返回格式

## 与其他原则的配合

### 与PR-007（统一的执行命令）配合

- 执行命令中的prompt字段传递给llm_call方法
- 返回值用于更新命令状态和生成输出

### 与PR-017（日志追踪）配合

- 每次LLM调用记录到llm_calls.jsonl
- 包含prompt、tokens、response_time等信息

### 与PR-020（命令完整性保证机制）配合

- 通过skill调用保证命令完整性
- skill使用generate_response生成结构化命令

## 使用示例

### 在Agent中使用

```python
from llm_communication import simple_llm_service

class Agent:
    def execute_command(self, command):
        # 构造提示词
        prompt = command['prompt']

        # 调用LLM
        response = simple_llm_service.llm_call(prompt)

        # 处理响应
        if response.startswith("调用失败"):
            # 处理错误
            return {"success": False, "error": response}

        # 成功
        return {"success": True, "result": response}
```

---

**最后更新**: 2025-01-08

