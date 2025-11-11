# MCP Proof Of Concept

Just a MCP Proof of Concept using

- Ollama,
- FastapiMCP for MCP over SSE
- A Simple Agent using exposed tools

# Usage

## Tools

- [Install UV](https://docs.astral.sh/uv/getting-started/installation/). Package manager

```shell
curl -LsSf https://astral.sh/uv/install.sh | sh
```
- Use [Direnv](https://direnv.net/docs/installation.html) for your environment vars
```shell
# On mac
brew install direnv
```
- Uses [Docker](https://docs.docker.com/desktop/). 

## How to run

1. Start your mcp server
```shell 
 docker-compose up --build
```

2. Run your local agent

```shell
cd mcpagent
# Just first time
uv sync
# Run Agent
uv run agent_runner.py
```

3. Sgut down your mcp demo server
```shell 
 docker-compose down
```


 