"""Fill a prompt template's {variable} placeholders with a test case's inputs."""
import re

VARIABLE_PATTERN = re.compile(r"\{(\w+)\}")


class MissingVariableError(Exception):
    def __init__(self, missing: list[str]):
        self.missing = missing
        super().__init__(f"missing input variables: {', '.join(missing)}")


def render(template: str, inputs: dict[str, str]) -> str:
    """'Reply to: {message}' + {'message': 'hola'} -> 'Reply to: hola'.

    Uses a regex instead of str.format() so literal braces in a template
    (for example a JSON example like {"reply": "..."}) don't break rendering.
    """
    missing = [name for name in VARIABLE_PATTERN.findall(template) if name not in inputs]
    if missing:
        raise MissingVariableError(list(dict.fromkeys(missing)))
    return VARIABLE_PATTERN.sub(lambda m: inputs[m.group(1)], template)
