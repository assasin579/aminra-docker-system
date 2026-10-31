"""Ensure selective integration cannot silently register an older duplicate route."""
import ast
from pathlib import Path


def test_submission_handler_and_route_names_are_unique():
    tree = ast.parse((Path(__file__).parents[1] / 'auth/submission_router.py').read_text())
    names = set()
    routes = set()
    for node in tree.body:
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        assert node.name not in names, f'duplicate handler: {node.name}'
        names.add(node.name)
        for decorator in node.decorator_list:
            if isinstance(decorator, ast.Call) and isinstance(decorator.func, ast.Attribute) and isinstance(decorator.func.value, ast.Name) and decorator.func.value.id == 'router':
                route = (decorator.func.attr, ast.literal_eval(decorator.args[0]))
                assert route not in routes, f'duplicate route: {route}'
                routes.add(route)
