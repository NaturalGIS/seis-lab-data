"""MkDocs hooks for PDF-only content injection"""


def on_page_markdown(markdown, page, config, files):
    live_url = config.get("extra", {}).get("live_url")
    if not live_url:
        return markdown
    note = (
        f'!!! note "Versão online"\n'
        f"    A versão atualizada deste documento está disponível em "
        f"[{live_url}]({live_url}).\n\n"
    )
    return note + markdown
