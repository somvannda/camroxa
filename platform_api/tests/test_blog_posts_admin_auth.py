"""Guard: admin blog routes must actually depend on require_admin.

A default of ``_: Any = require_admin`` is not a FastAPI dependency, so the
handler runs with no auth. Use ``AdminDep = Annotated[..., Depends(require_admin)]``.
"""

from __future__ import annotations

from fastapi.routing import APIRoute

from platform_api.middleware.auth import require_admin
from platform_api.routers.blog_posts import router


def _dependency_calls(dependant: object) -> list[object]:
    found: list[object] = []
    stack = [dependant]
    seen: set[int] = set()
    while stack:
        current = stack.pop()
        ident = id(current)
        if ident in seen:
            continue
        seen.add(ident)
        call = getattr(current, "call", None)
        if call is not None:
            found.append(call)
        stack.extend(getattr(current, "dependencies", []) or [])
    return found


def test_admin_blog_routes_require_admin_dependency() -> None:
    admin_routes = [
        route
        for route in router.routes
        if isinstance(route, APIRoute) and route.path.startswith("/admin/blog-posts")
    ]
    assert {tuple(sorted(route.methods)) for route in admin_routes} >= {
        ("GET",),
        ("POST",),
        ("PUT",),
        ("DELETE",),
    }
    for route in admin_routes:
        assert require_admin in _dependency_calls(route.dependant), (
            f"{sorted(route.methods)} {route.path} is missing Depends(require_admin)"
        )


def test_public_blog_routes_do_not_require_admin() -> None:
    public_routes = [
        route
        for route in router.routes
        if isinstance(route, APIRoute) and "/blog-posts/public" in route.path
    ]
    assert public_routes
    for route in public_routes:
        assert require_admin not in _dependency_calls(route.dependant)
