"""The @tool decorator provides one definition for name, schema, and dispatch.

    from pokelike.bot.llm import LLMBot, tool

    class MyBot(LLMBot):
        @tool("What you are carrying, by name.")
        def bag(self, state) -> str:
            return ", ".join(state.get("bag") or []) or "(nothing)"

        @tool("Which of your move types beat a type you name.",
              against="the defending type, one word")
        def beats(self, state, against: str) -> str:
            ...

The method name becomes the tool name. The first positional argument is the
description. Keyword arguments describe parameters, and their JSON type comes
from the annotation. Parameters without a default are required.
"""

from __future__ import annotations

import inspect
from typing import Any, Callable

# Marker attribute set on decorated methods.
_TOOL_MARKER = "__llm_tool__"

# Python type annotation -> JSON Schema type string.
_TYPE_MAP: dict[type, str] = {
    str: "string",
    int: "integer",
    float: "number",
    bool: "boolean",
}


def tool(description: str, **param_docs: str) -> Callable:
    """Marks a method as an LLM tool with its schema derived from the signature."""

    def decorator(fn: Callable) -> Callable:
        sig = inspect.signature(fn)
        params = list(sig.parameters.keys())
        # Skip `self` and `state` (the first two positional args).
        tool_params = params[2:]  # everything after self, state

        properties: dict[str, dict[str, str]] = {}
        required: list[str] = []

        for name in tool_params:
            p = sig.parameters[name]
            # Derive the JSON type from the Python annotation.
            ann = p.annotation
            json_type = _TYPE_MAP.get(ann, "string") if ann is not inspect.Parameter.empty else "string"
            prop: dict[str, str] = {"type": json_type}
            if name in param_docs:
                prop["description"] = param_docs[name]
            properties[name] = prop
            # A parameter is required if it has no default value.
            if p.default is inspect.Parameter.empty:
                required.append(name)

        schema: dict[str, Any] = {
            "type": "function",
            "function": {
                "name": fn.__name__,
                "description": description,
                "parameters": {"type": "object", "properties": properties},
            },
        }
        if required:
            schema["function"]["parameters"]["required"] = required

        setattr(fn, _TOOL_MARKER, schema)
        return fn

    return decorator


def collect_decorated_tools(cls: type) -> list[dict[str, Any]]:
    """Collects tool schemas from all @tool-decorated methods on a class.

    Later definitions (lower in the MRO) override earlier ones of the same name.
    """
    # Walk the MRO so subclass methods override parent methods of the same name.
    seen_names: dict[str, dict[str, Any]] = {}
    for klass in reversed(cls.__mro__):
        for attr_name, attr_val in vars(klass).items():
            if callable(attr_val) and hasattr(attr_val, _TOOL_MARKER):
                schema = getattr(attr_val, _TOOL_MARKER)
                seen_names[schema["function"]["name"]] = schema
    # Return in definition order of the final class (the order a reader sees).
    ordered: list[dict[str, Any]] = []
    for klass in cls.__mro__:
        for attr_name in vars(klass):
            attr_val = vars(klass)[attr_name]
            if callable(attr_val) and hasattr(attr_val, _TOOL_MARKER):
                name = getattr(attr_val, _TOOL_MARKER)["function"]["name"]
                if name in seen_names:
                    ordered.append(seen_names.pop(name))
    return ordered


def dispatch_decorated_tool(
    bot: Any, name: str, args: dict[str, Any], state: dict[str, Any]
) -> str | None:
    """Dispatches a tool call to a @tool-decorated method, if one matches.

    Returns the result string, or None if no decorated method handles this name.
    """
    # Walk the MRO to find the method (subclass wins).
    for klass in type(bot).__mro__:
        for attr_name in vars(klass):
            attr_val = vars(klass)[attr_name]
            if (callable(attr_val)
                    and hasattr(attr_val, _TOOL_MARKER)
                    and getattr(attr_val, _TOOL_MARKER)["function"]["name"] == name):
                try:
                    result = attr_val(bot, state, **args)
                    return str(result) if result is not None else ""
                except Exception as exc:  # noqa: BLE001
                    return f"error in {name}: {type(exc).__name__}: {exc}"
    return None
