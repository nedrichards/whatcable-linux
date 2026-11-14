"""Build an offline contact sheet from fixture-only CI captures."""

import html
from pathlib import Path

root = Path(".ci-results")
items = []
for path in sorted(root.rglob("*.png")):
    name = html.escape(path.relative_to(root).as_posix(), quote=True)
    items.append(
        f'<figure><a href="{name}"><img loading="lazy" src="{name}" alt="{name}"></a><figcaption>{name}</figcaption></figure>'
    )
for path in sorted(root.glob("*.pdf")):
    name = html.escape(path.name, quote=True)
    items.append(f'<p><a href="{name}">Rendered fixture: {name}</a></p>')
root.mkdir(exist_ok=True)
(root / "index.html").write_text(
    '<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>Native CI review</title><style>body{font:16px system-ui;margin:2rem}main{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:1rem}figure{margin:0}img{width:100%;height:360px;object-fit:contain}</style><h1>Native CI review</h1><p>Fixture captures for review; no physical-input or hardware acceptance is claimed.</p><main>'
    + "".join(items)
    + "</main></html>\n",
    encoding="utf-8",
)
