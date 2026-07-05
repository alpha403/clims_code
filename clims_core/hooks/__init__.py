"""Event hooks — run user-configured commands on agent lifecycle events.

Hooks let the user (or enterprise policy) observe and gate the agent: block a
dangerous tool call, inject context on prompt submit, audit-log every tool, etc.
Configured in settings under "hooks". The harness executes them, not the model.
"""
from clims_core.hooks.runner import HookRunner, HookOutcome

__all__ = ["HookRunner", "HookOutcome"]
