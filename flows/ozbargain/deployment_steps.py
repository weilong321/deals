import os


def set_environment_variables(
    env: dict[str, str] | None = None,
) -> dict[str, list[str]]:
    variables = env or {}
    os.environ.update(variables)
    return {"variables": list(variables)}
