import asyncio
import os
from datetime import datetime, timezone
from typing import List

from dotenv import load_dotenv
from langchain.tools import tool
from langchain_ollama import ChatOllama

from utils.best_efort_encoder import best_effort_serialize

# Load environment variables from .env file
load_dotenv(
    dotenv_path="local.env"
    if os.getenv("ENV") in ("development", "dev", "local")
    else None
)


@tool
def validate_user(user_id: int, addresses: List[str]) -> bool:
    """Validate user using historical addresses.

    Args:
        user_id (int): the user ID.
        addresses (List[str]): Previous addresses as a list of strings.
    """
    return True


async def main() -> None:
    llm = ChatOllama(
        model=os.getenv("OLLAMA_MODEL", "qwen3:8b"),
        base_url=os.getenv("OLLAMA_SERVER_URL", "http://localhost:11434"),
        validate_model_on_init=True,
        temperature=0,
    ).bind_tools([validate_user])

    result = llm.invoke(
        "Could you validate user 123? They previously lived at "
        "123 Fake St in Boston MA and 234 Pretend Boulevard in "
        "Houston TX."
    )

    print(best_effort_serialize(result))

    if getattr(result, "tool_calls", None):
        print(result.tool_calls)


if __name__ == "__main__":
    print(f"[{datetime.now(timezone.utc).isoformat()}] Program started.")
    asyncio.run(main())  # Run the main asynchronous function
    print(f"[{datetime.now(timezone.utc).isoformat()}] Program finished  .")
