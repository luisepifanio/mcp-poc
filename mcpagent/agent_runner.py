# Use server from examples/servers/streamable-http-stateless/
import asyncio
import os
import time

from dotenv import load_dotenv
from langchain.agents import create_agent  # pyright: ignore[reportUnknownVariableType]
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import BaseTool
from langchain_mcp_adapters.client import MultiServerMCPClient  # pyright: ignore[reportMissingTypeStubs]
from langchain_ollama import ChatOllama
from pyfiglet import Figlet

from utils.best_efort_encoder import best_effort_serialize
from utils.spinner import Spinner

# Load environment variables from .env file
load_dotenv(
    dotenv_path="local.env"
    if os.getenv("ENV") in ("development", "dev", "local")
    else None
)


async def main() -> None:
    f = Figlet(font="standard")
    print(f.renderText("Nyx Agent🦉 v 0.0.1"))
    x = input("Ask Nyx Agent 🦉\n")

    client = MultiServerMCPClient(
        {
            "local": {
                "transport": "sse",
                "url": os.getenv("LOCAL_MCP_URL", "http://127.0.0.1:3000/mcp"),
            }
        }
    )
    tools: list[BaseTool] = await client.get_tools()

    llm = ChatOllama(
        model=os.getenv("OLLAMA_MODEL", "qwen3:8b"),
        base_url=os.getenv("OLLAMA_SERVER_URL", "http://localhost:11434"),
    )

    #  client = Client(api_key=os.getenv("LANGSMITH_API_KEY"))
    # system_prompt = client.pull_prompt("hwchase17/react", include_model=True)

    agent = create_agent(
        model=llm,
        tools=tools,
        system_prompt="You are a helpful assistant",
    )

    result = None

    s = Spinner("Reasoning | Choosing tools | Gathering info")
    try:
        config = RunnableConfig(tags=["debug", "local"], recursion_limit=100)

        s.start()
        result = await agent.ainvoke(
            {"messages": [{"role": "user", "content": x}]}, config=config
        )
        s.stop(success=True)
    except Exception:
        s.stop(success=False)
        raise

    final = result["messages"][-1].content

    print(final)
    print("---")
    print(best_effort_serialize(result))
    # print("---")
    # pprint(result, indent=2)


if __name__ == "__main__":
    print(f"[{time.strftime('%X')}] Program started.")
    asyncio.run(main())  # Run the main asynchronous function
    print(f"[{time.strftime('%X')}] Program finished.")
