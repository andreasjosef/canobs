"""Canvas HTML -> clean markdown."""
import re

from markdownify import markdownify


def to_markdown(html: str) -> str:
    md = markdownify(
        html,
        heading_style="ATX",
        bullets="-",
        newline_style="BACKSLASH",
        strip=["script", "style", "span", "div", "iframe"],
    )
    md = md.replace(" ", " ")
    md = re.sub(r"[ \t]+\n", "\n", md)       # trailing spaces
    md = re.sub(r"\n{3,}", "\n\n", md)       # max one blank line
    return md.strip() + "\n"
