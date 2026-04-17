import asyncio
import warnings
from typing import Any, Optional
from datetime import datetime, timedelta, timezone
from collections import deque

# Suppress deprecation warning for google.generativeai
# TODO: Migrate to google.genai package when stable
warnings.filterwarnings('ignore', message='.*google.generativeai.*')
import google.generativeai as genai

from src.config import settings
from src.utils.logger import setup_logger

logger = setup_logger(__name__)


class RateLimiter:
    def __init__(self, max_requests: int, time_window: int = 60):
        self.max_requests = max_requests
        self.time_window = time_window
        self.requests: deque[datetime] = deque()

    async def acquire(self) -> None:
        """Acquire rate limiter token, waiting if necessary."""
        now = datetime.now(timezone.utc)
        cutoff = now - timedelta(seconds=self.time_window)

        while self.requests and self.requests[0] < cutoff:
            self.requests.popleft()

        while len(self.requests) >= self.max_requests:
            oldest = self.requests[0]
            wait_time = (oldest + timedelta(seconds=self.time_window) - now).total_seconds()
            if wait_time > 0:
                logger.debug(f"Rate limit reached, waiting {wait_time:.2f} seconds")
                await asyncio.sleep(wait_time)
            now = datetime.now(timezone.utc)
            cutoff = now - timedelta(seconds=self.time_window)
            while self.requests and self.requests[0] < cutoff:
                self.requests.popleft()

        self.requests.append(now)


class LLMGateway:
    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        rate_limit: int | None = None,
    ):
        self.api_key = api_key or settings.gemini_api_key
        self.model_name = model or settings.gemini_model
        self.rate_limiter = RateLimiter(
            rate_limit or settings.rate_limit_requests_per_minute
        )

        genai.configure(api_key=self.api_key)
        self.model = genai.GenerativeModel(self.model_name)

        self.request_log: list[dict[str, Any]] = []

    async def generate(
        self,
        prompt: str,
        agent_id: str,
        task_type: str,
        temperature: float = 0.7,
        max_tokens: int | None = None,
    ) -> str:
        """Generate content using LLM with error handling and rate limiting."""
        try:
            await self.rate_limiter.acquire()

            generation_config = genai.GenerationConfig(
                temperature=temperature,
                max_output_tokens=max_tokens,
            )

            logger.debug(f"Generating content for agent={agent_id}, task={task_type}")
            response = await self.model.generate_content_async(
                prompt, generation_config=generation_config
            )

            response_text = response.text if response.text else ""

            self.request_log.append(
                {
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "agent_id": agent_id,
                    "task_type": task_type,
                    "prompt_length": len(prompt),
                    "response_length": len(response_text),
                }
            )

            logger.debug(f"Generated {len(response_text)} chars for {task_type}")
            return response_text

        except Exception as e:
            logger.error(f"LLM generation failed for {agent_id}/{task_type}: {e}")
            raise

    async def generate_with_context(
        self,
        system_prompt: str,
        user_prompt: str,
        context: str,
        agent_id: str,
        task_type: str,
        temperature: float = 0.7,
    ) -> str:
        full_prompt = f"{system_prompt}\n\n# Context\n{context}\n\n# Task\n{user_prompt}"
        return await self.generate(full_prompt, agent_id, task_type, temperature)

    def get_stats(self) -> dict[str, Any]:
        if not self.request_log:
            return {
                "total_requests": 0,
                "by_agent": {},
                "by_task_type": {},
            }

        by_agent: dict[str, int] = {}
        by_task_type: dict[str, int] = {}

        for log in self.request_log:
            agent_id = log["agent_id"]
            task_type = log["task_type"]

            by_agent[agent_id] = by_agent.get(agent_id, 0) + 1
            by_task_type[task_type] = by_task_type.get(task_type, 0) + 1

        return {
            "total_requests": len(self.request_log),
            "by_agent": by_agent,
            "by_task_type": by_task_type,
        }
