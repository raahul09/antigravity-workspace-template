# 🚀 快速开始指南

几分钟内运行 Antigravity Workspace Template。

## 📋 前置条件

- Python 3.9+
- pip 或 conda
- Git

## 🏃 本地开发

### 1. 安装依赖
```bash
pip install -e .
```

### 2. 运行 Agent
```bash
ag-engine
```

该命令每次执行一个任务，并会自动：
- 🧠 从 `memory/agent_memory.md` 加载记忆
- 🛠️ 发现 `antigravity_engine/tools/` 里的工具
- 📚 注入 `.context/` 的知识

### 3. 使用示例
```bash
ag-engine "帮我写一个计算斐波那契数列的 Python 函数"
```

Agent 会执行该任务并将结果输出到终端。

## 🐳 Docker 部署

### 构建与运行
```bash
docker-compose up --build
```

这会：
- 安装依赖
- 在容器中启动 Agent
- 挂载你的工作区便于实时编辑

可按需修改 `docker-compose.yml`（环境变量、挂载卷、端口等）。

## 🔧 配置

### 环境变量
创建 `.env`：

```bash
# LLM 配置
GOOGLE_API_KEY=your-api-key-here
GEMINI_MODEL_NAME=gemini-2.0-flash-exp

# MCP 配置
MCP_ENABLED=true

# 自定义
LOG_LEVEL=INFO
ARTIFACTS_DIR=artifacts
```

`ARTIFACTS_DIR` 支持绝对路径和相对路径。相对路径会基于仓库根目录解析，
避免输出落到 IDE 的默认目录。

### 记忆管理
记忆由以下 Markdown 文件自动管理：
- `memory/agent_memory.md`（原始记忆条目）
- `memory/agent_summary.md`（压缩摘要）

重置方法：

```bash
rm -f memory/agent_memory.md memory/agent_summary.md
ag-engine
```

## 📁 项目结构参考

```
├── antigravity_engine/
│   ├── agent.py         # 主循环
│   ├── config.py        # 配置管理
│   ├── memory.py        # 记忆引擎
│   ├── agents/          # 专家型 Agent
│   └── tools/           # 工具实现
├── artifacts/           # 输出 artifacts
├── .context/            # 知识库
└── .antigravity/        # Antigravity 规则
```

详见 [项目结构](README.md)。

## 🧪 运行测试

```bash
# 全量
pytest

# 指定文件
pytest tests/test_agent.py -v

# 覆盖率
pytest --cov=antigravity_engine tests/
```

## 🐛 常见问题

### Agent 无法启动
```bash
# 检查依赖
pip list | grep -Ei "google-genai|google-generativeai"

# 检查 GOOGLE_API_KEY
echo $GOOGLE_API_KEY
```

### 工具未加载
```bash
# 检查 antigravity_engine/tools/ 文件
ls -la antigravity_engine/tools/

# 检查语法
python -m py_compile antigravity_engine/tools/*.py
```

### 记忆异常
```bash
# 查看记忆
cat memory/agent_memory.md

# 清理记忆
rm -f memory/agent_memory.md memory/agent_summary.md
```

## 🔌 MCP 集成

启用步骤：
1. `.env` 中设置 `MCP_ENABLED=true`  
2. 在 `mcp_servers.json` 配置服务器  
3. 重启 Agent  

详见 [MCP 集成指南](MCP_INTEGRATION.md)。

## 📚 下一步

- **了解理念**： [项目理念](PHILOSOPHY.md)  
- **探索 MCP**： [MCP 集成](MCP_INTEGRATION.md)  
- **多 Agent**： [Swarm 协议](SWARM_PROTOCOL.md)  
- **高级特性**： [零配置特性](ZERO_CONFIG.md)  
- **规划路线**： [开发路线图](ROADMAP.md)  

---

更多信息参见 [文档索引](README.md) 或在 GitHub 提 Issue。👍
