from __future__ import annotations


def test_app_registers_current_user_modules_router():
    from app import app

    included = [route for route in app.routes if route.__class__.__name__ == "_IncludedRouter"]
    module_includes = [
        route for route in included
        if getattr(route, "include_context", None)
        and route.include_context.prefix == "/api/me"
        and "modules" in route.include_context.tags
    ]

    assert len(module_includes) == 1
    assert any(
        child.path == "/modules" and child.methods == {"GET"}
        for child in module_includes[0].original_router.routes
    )
