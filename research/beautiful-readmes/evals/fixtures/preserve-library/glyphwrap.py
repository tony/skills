import textwrap


def wrap(text: str, width: int = 70) -> list[str]:
    return textwrap.wrap(text, width=width)
