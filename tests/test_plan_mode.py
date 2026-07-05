"""Plan mode: research-only (read + web), blocks changes (write/edit/shell)."""
from clims_core.permissions.policy import (
    PermissionPolicy, PermissionMode, PermissionClass, Decision,
)


def test_plan_mode_allows_research_blocks_changes():
    p = PermissionPolicy(mode=PermissionMode.PLAN)
    # research is allowed
    assert p.decide("read", PermissionClass.READ_ONLY, {}) == Decision.ALLOW
    assert p.decide("grep", PermissionClass.READ_ONLY, {}) == Decision.ALLOW
    assert p.decide("web_search", PermissionClass.NETWORK, {}) == Decision.ALLOW
    assert p.decide("web_fetch", PermissionClass.NETWORK, {}) == Decision.ALLOW
    # documenting the plan is allowed (markdown + memory), code changes are not
    assert p.decide("write", PermissionClass.MUTATING, {"path": "plan.md"}) == Decision.ALLOW
    assert p.decide("write", PermissionClass.MUTATING, {"path": "DECISIONS.md"}) == Decision.ALLOW
    assert p.decide("memory", PermissionClass.MUTATING, {"command": "write"}) == Decision.ALLOW
    # code / shell are blocked
    assert p.decide("write", PermissionClass.MUTATING, {"path": "app.py"}) == Decision.DENY
    assert p.decide("edit", PermissionClass.MUTATING, {"path": "index.html"}) == Decision.DENY
    assert p.decide("bash", PermissionClass.EXEC, {"command": "ls"}) == Decision.DENY
