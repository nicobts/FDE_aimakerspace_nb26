def assign_tier(work: dict) -> str:
    # Decided from fields only: whether the PDF URL really serves a PDF is checked
    # when the file is fetched, so the seed run makes no publisher requests.
    # An empty abstract counts as missing, since there is nothing to embed.
    if not work.get("abstract"):
        return "metadata"
    if not work.get("pdf_url"):
        return "abstract"
    return "pdf"
