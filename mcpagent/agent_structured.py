import asyncio
import os
from datetime import datetime, timezone

from langchain.agents import create_agent
from langchain.agents.structured_output import ToolStrategy
from langchain_ollama import ChatOllama
from pydantic import BaseModel
from typing import Any

from utils.best_efort_encoder import best_effort_serialize


class ContactInfo(BaseModel):
    name: str
    email: str
    phone: str


def empty_pass_tool(query: str) -> str:
    """Run a search."""
    pass


async def main() -> None:
    llm = ChatOllama(
        model=os.getenv("OLLAMA_MODEL", "qwen3:8b"),
        base_url=os.getenv("OLLAMA_SERVER_URL", "http://localhost:11434"),
    )

    agent = create_agent(
        model=llm,
        tools=[empty_pass_tool],
        system_prompt="you are an expert in extracting data",
        response_format=ToolStrategy(ContactInfo),  # 🟢 This is important
    )

    result = agent.invoke(
        {
            "messages": [
                {
                    "role": "user",
                    "content": "Extract contact info from: John Doe, john@example.com, (555) 123-4567",
                }
            ]
        }
    )
    # print(best_effort_serialize(result))

    # 'agent.invoke' returns a dict; handle both dict-structured_response and BaseModel
    if isinstance(result, dict) and "structured_response" in result:
        sr: ContactInfo | dict[str, Any] = result["structured_response"]
        structured: ContactInfo | None = None
        if isinstance(sr, ContactInfo):
            print("Structured Response is already a ContactInfo")
            structured = sr
        elif isinstance(sr, dict):
            # Convert dict to ContactInfo model (pydantic v2)
            print("Structured Response is a dict, converting to BaseModel")
            structured = ContactInfo.model_validate(sr)

        if structured is not None:
            print("Structured Response:", str(structured))
            print(structured.model_dump(mode="json"))


if __name__ == "__main__":
    print(f"[{datetime.now(timezone.utc).isoformat()}] Program started.")
    asyncio.run(main())  # Run the main asynchronous function
    print(f"[{datetime.now(timezone.utc).isoformat()}] Program finished  .")
