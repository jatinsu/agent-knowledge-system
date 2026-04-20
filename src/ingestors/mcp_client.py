import json
from contextlib import AsyncExitStack
from typing import Any

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from src.utils.logger import setup_logger

logger = setup_logger(__name__)


class MCPClient:
    """Manages a connection to an MCP server over stdio transport."""

    def __init__(
        self,
        command: str,
        args: list[str],
        env: dict[str, str] | None = None,
    ):
        self._server_params = StdioServerParameters(
            command=command, args=args, env=env
        )
        self._session: ClientSession | None = None
        self._stack: AsyncExitStack | None = None

    async def __aenter__(self) -> "MCPClient":
        self._stack = AsyncExitStack()
        read, write = await self._stack.enter_async_context(
            stdio_client(self._server_params)
        )
        self._session = await self._stack.enter_async_context(
            ClientSession(read, write)
        )
        await self._session.initialize()
        logger.info(f"Connected to MCP server: {self._server_params.command} {' '.join(self._server_params.args)}")
        return self

    async def __aexit__(self, *exc: Any) -> None:
        if self._stack:
            await self._stack.aclose()
        self._session = None
        self._stack = None

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> Any:
        """Call a tool on the connected MCP server and return parsed JSON."""
        if not self._session:
            raise RuntimeError("Not connected — use 'async with' to manage lifecycle")

        result = await self._session.call_tool(name, arguments)

        if result.isError:
            error_text = result.content[0].text if result.content else "Unknown error"
            raise RuntimeError(f"MCP tool '{name}' failed: {error_text}")

        if result.content:
            text = result.content[0].text
            try:
                return json.loads(text)
            except (json.JSONDecodeError, TypeError):
                return text

        return None
