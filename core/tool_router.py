"""
Novel-Claude Fusion — Tool Router (Agent Loop)

Bridges the gap between skills defining get_llm_tools()/execute_tool()
and actual LLM-driven execution. Implements the minimal agent loop:

  System Prompt + User Message + Tool Schemas -> LLM
      |
      v
  If tool_calls -> route to skill.execute_tool() -> feed results back -> LLM
      |
      v
  If text response -> return final answer

Pattern: 2026 industry standard (LangChain "Loop 1", allegro-agent, exoclaw-turn)
Max iterations: 10 (configurable)
"""

from __future__ import annotations

import json
from typing import List, Dict, Any, Optional, Callable

from utils.llm_client import _get_client, resolve_provider, resolve_model


class ToolRouter:
    """
    Minimal agent loop that routes LLM tool calls to Skill.execute_tool().

    Usage:
        router = ToolRouter(skills=[gold_finger_skill, ...])
        result = router.run("升级主角的烈焰掌技能")
        # LLM may call simplify_skill tool, router routes to gold_finger.execute_tool()
    """

    def __init__(self, skills: list = None, max_iterations: int = 10,
                 temperature: float = 0.7, model_override: str = None):
        self.skills = skills or []
        self.max_iterations = max_iterations
        self.temperature = temperature
        self.model_override = model_override
        self.call_history: List[Dict[str, Any]] = []

    # ── public API ──────────────────────────────────────────────────────────

    def run(self, user_prompt: str,
            system_message: str = None,
            extra_tools: List[Dict] = None) -> str:
        """
        Run the agent loop with tool calling.

        Args:
            user_prompt: The user's request
            system_message: Optional system prompt
            extra_tools: Additional tool schemas (beyond skills' get_llm_tools())

        Returns:
            Final text response from LLM, or error message if loop exceeded.
        """
        # Build tool schemas
        tool_schemas = self._collect_tools(extra_tools)

        # Build messages
        messages = []
        if system_message:
            messages.append({"role": "system", "content": system_message})
        messages.append({"role": "user", "content": user_prompt})

        # Agent loop
        for iteration in range(self.max_iterations):
            response = self._call_llm(messages, tool_schemas)

            msg = response.choices[0].message

            # Check for tool calls
            if getattr(msg, 'tool_calls', None) and len(msg.tool_calls) > 0:
                # Record assistant message
                assistant_msg = {"role": "assistant"}
                if msg.content:
                    assistant_msg["content"] = msg.content
                assistant_msg["tool_calls"] = [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {"name": tc.function.name, "arguments": tc.function.arguments},
                    }
                    for tc in msg.tool_calls
                ]
                messages.append(assistant_msg)

                # Execute each tool call
                for tc in msg.tool_calls:
                    tool_name = tc.function.name
                    try:
                        tool_args = json.loads(tc.function.arguments)
                    except json.JSONDecodeError:
                        tool_args = {}

                    result = self._execute_tool(tool_name, tool_args)
                    self.call_history.append({
                        "iteration": iteration + 1,
                        "tool": tool_name,
                        "args": tool_args,
                        "result": result[:200],
                    })

                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "name": tool_name,
                        "content": result,
                    })

                continue  # Loop back to LLM with tool results

            # No tool calls — final text response
            result = msg.content or ""
            return result

        return f"[ToolRouter] Max iterations ({self.max_iterations}) exceeded. Last call history: {json.dumps(self.call_history[-3:], ensure_ascii=False)}"

    def run_with_retry(self, user_prompt: str, system_message: str = None,
                       extra_tools: List[Dict] = None, max_retries: int = 2) -> str:
        """Run with automatic retry on empty result."""
        for attempt in range(max_retries):
            result = self.run(user_prompt, system_message, extra_tools)
            if result and len(result.strip()) > 10:
                return result
            if attempt < max_retries - 1:
                print(f"  [ToolRouter] Retry {attempt + 1}/{max_retries}: empty response")
        return result

    # ── tool management ─────────────────────────────────────────────────────

    def _collect_tools(self, extra_tools: List[Dict] = None) -> List[Dict]:
        """Collect tool schemas from all registered skills + extras."""
        tools = list(extra_tools or [])
        seen_names = set()

        for skill in self.skills:
            if hasattr(skill, 'get_llm_tools'):
                try:
                    skill_tools = skill.get_llm_tools()
                    for tool in skill_tools:
                        name = tool.get("function", {}).get("name", "")
                        if name and name not in seen_names:
                            tools.append(tool)
                            seen_names.add(name)
                except Exception as e:
                    print(f"  [ToolRouter] Warning: {skill.name} get_llm_tools() failed: {e}")

        return tools

    def _execute_tool(self, tool_name: str, kwargs: dict) -> str:
        """Route tool call to the correct skill's execute_tool()."""
        for skill in self.skills:
            if hasattr(skill, 'execute_tool'):
                try:
                    result = skill.execute_tool(tool_name, kwargs)
                    if result:  # Non-empty result means the skill handled it
                        return str(result)
                except Exception as e:
                    return f"[Error] {skill.name}.execute_tool('{tool_name}') failed: {e}"

        return f"[Error] No skill registered to handle tool '{tool_name}'. Available: {self._list_tool_names()}"

    def _list_tool_names(self) -> List[str]:
        """List all tool names from registered skills."""
        names = []
        for skill in self.skills:
            if hasattr(skill, 'get_llm_tools'):
                for tool in skill.get_llm_tools():
                    names.append(tool.get("function", {}).get("name", "?"))
        return names

    def _call_llm(self, messages: List[Dict], tool_schemas: List[Dict]):
        """Call LLM with messages + tool schemas."""
        client = _get_client()
        provider = resolve_provider()
        model = self.model_override or resolve_model(provider)

        kwargs = {
            "model": model,
            "messages": messages,
            "temperature": self.temperature,
        }
        if tool_schemas:
            kwargs["tools"] = tool_schemas
            kwargs["tool_choice"] = "auto"

        return client.chat.completions.create(**kwargs)
