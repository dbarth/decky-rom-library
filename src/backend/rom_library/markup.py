"""Just enough XML for ES-DE's files. Decky's Python ships without xml.etree."""
import html
import re

COMMENT = re.compile(r"<!--.*?-->", re.S)
ATTRIBUTE = re.compile(r"""([\w:.-]+)\s*=\s*(?:"([^"]*)"|'([^']*)')""")


def clean(text):
    return COMMENT.sub("", text)


def elements(text, tag):
    """Yield (attributes, inner text) for each <tag> element, self-closing ones included.

    Elements of the same tag must not nest, which holds for every file ES-DE writes."""
    pattern = re.compile(r"<%s(\s[^>]*?)?(?:/>|>(.*?)</%s\s*>)" % (re.escape(tag), re.escape(tag)), re.S)
    for m in pattern.finditer(text):
        yield attributes(m.group(1) or ""), m.group(2) or ""


def attributes(text):
    return {m.group(1): html.unescape(m.group(2) if m.group(2) is not None else m.group(3))
            for m in ATTRIBUTE.finditer(text)}


def texts(inner, tag):
    """Return the unescaped, stripped text of each <tag> child."""
    return [html.unescape(body).strip() for _, body in elements(inner, tag)]


def text(inner, tag, default=None):
    found = texts(inner, tag)
    return found[0] if found else default
