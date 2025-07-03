import re

from rich.text import Text


def slugify(value: str) -> str:
    """
    Converts a given string into a slug format. The slug format is typically
    used for URLs, where spaces are replaced with hyphens and all characters
    are converted to lowercase.

    :param value: The string to be converted into slug format.
    :type value: str
    :return: A slugified version of the input string.
    :rtype: str
    """
    return re.sub(r"[^a-z0-9-]", "", value.lower().replace(" ", "-"))


def build_logo() -> Text:
    """
    Builds and returns an ASCII art logo styled with specific colors and text formats.
    The function creates a stylized representation of a logo using the ``Text`` object.
    Each line of the logo is appended to the text object with a distinct style, alternating
    between bold cyan and bold blue.

    :return: Styled ASCII art logo representation.
    :rtype: Text
    """
    ascii_art_logo = Text()
    ascii_art_logo.append(
        "\n ██████  ██████  ███████ ███    ███ ██ ████████ ██   ██\n", style="bold cyan"
    )
    ascii_art_logo.append(
        "██    ██ ██   ██ ██      ████  ████ ██    ██    ██   ██\n", style="bold blue"
    )
    ascii_art_logo.append(
        "██    ██ ██████  ███████ ██ ████ ██ ██    ██    ███████\n", style="bold cyan"
    )
    ascii_art_logo.append(
        "██    ██ ██           ██ ██  ██  ██ ██    ██    ██   ██\n", style="bold blue"
    )
    ascii_art_logo.append(
        " ██████  ██      ███████ ██      ██ ██    ██    ██   ██\n\n", style="bold cyan"
    )
    return ascii_art_logo
