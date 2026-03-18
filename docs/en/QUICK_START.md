# 🚀 Quick Start Guide

Get up and running with the Antigravity Workspace Template in minutes.

## 📋 Prerequisites

- Python 3.9+
- pip or conda
- Git

## 🏃 Local Development

### 1. Install Dependencies
```bash
pip install -e .
```

### 2. Run the Agent
```bash
ag-engine
```

The agent runs a single task per invocation. It automatically:
- 🧠 Loads memory from `memory/agent_memory.md`
- 🛠️ Discovers tools in `antigravity_engine/tools/`
- 📚 Ingests context from `.context/`

### 3. Example Usage
```bash
ag-engine "Build a Python function to calculate Fibonacci numbers"
```

The agent will execute that task and print the result to stdout.

## 🐳 Docker Deployment

### Build & Run
```bash
docker-compose up --build
```

This will:
- Install all dependencies
- Start the agent in a containerized environment
- Mount your workspace for live code editing

Access the agent via the exposed interface.

### Customizing Docker
Edit `docker-compose.yml` to:
- Change environment variables
- Mount additional volumes
- Expose different ports

## 🔧 Configuration

### Environment Variables
Create a `.env` file:

```bash
# LLM Configuration
GOOGLE_API_KEY=your-api-key-here
GEMINI_MODEL_NAME=gemini-2.0-flash-exp

# MCP Configuration
MCP_ENABLED=true

# Custom settings
LOG_LEVEL=INFO
ARTIFACTS_DIR=artifacts
```

`ARTIFACTS_DIR` supports absolute or relative paths. Relative values are
resolved from the repository root so outputs do not drift into IDE default paths.

### Memory Management
The agent automatically manages memory via markdown files:
- `memory/agent_memory.md` (raw entries)
- `memory/agent_summary.md` (compressed summary)

To reset:

```bash
rm -f memory/agent_memory.md memory/agent_summary.md
ag-engine
```

## 📁 Project Structure Reference

```
├── antigravity_engine/
│   ├── agent.py         # Main agent loop
│   ├── config.py        # Configuration management
│   ├── memory.py        # Memory engine
│   ├── agents/          # Specialist agents
│   └── tools/           # Tool implementations
├── artifacts/           # Output artifacts
├── .context/            # Knowledge base
└── .antigravity/        # Antigravity rules
```

See [Project Structure](../README.md#project-structure) for details.

## 🧪 Running Tests

```bash
# Run all tests
pytest

# Run specific test
pytest tests/test_agent.py -v

# With coverage
pytest --cov=antigravity_engine tests/
```

## 🐛 Troubleshooting

### Agent doesn't start
```bash
# Check if dependencies are installed
pip list | grep -Ei "google-genai|google-generativeai"

# Verify GOOGLE_API_KEY is set
echo $GOOGLE_API_KEY
```

### Tools not loading
```bash
# Verify antigravity_engine/tools/ has valid Python files
ls -la antigravity_engine/tools/

# Check for syntax errors
python -m py_compile antigravity_engine/tools/*.py
```

### Memory issues
```bash
# Check memory file
cat memory/agent_memory.md

# Clear memory
rm -f memory/agent_memory.md memory/agent_summary.md
```

## 🔌 MCP Integration

To enable MCP servers:

1. Set `MCP_ENABLED=true` in `.env`
2. Configure servers in `mcp_servers.json`
3. Restart the agent

See [MCP Integration Guide](MCP_INTEGRATION.md) for detailed setup.

## 📚 Next Steps

- **Learn Philosophy**: [Project Philosophy](PHILOSOPHY.md)
- **Explore MCP**: [MCP Integration](MCP_INTEGRATION.md)
- **Multi-Agent**: [Swarm Protocol](SWARM_PROTOCOL.md)
- **Advanced**: [Zero-Config Features](ZERO_CONFIG.md)
- **Roadmap**: [Development Roadmap](ROADMAP.md)

---

**Questions?** Check the [Full Index](README.md) or open an issue on GitHub.
