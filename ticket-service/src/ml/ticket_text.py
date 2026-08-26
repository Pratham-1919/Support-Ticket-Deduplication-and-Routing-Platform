"""
Single source of truth for how ticket title+description are turned into
embeddable text. BOTH embedding_generator.py and similarity_search.py
must import and use this exact function -- any difference in wording
between the two silently corrupts similarity scores, because the model
treats a different label prefix as real semantic content.
"""

def build_ticket_text(title, description):
    title = "" if title is None else str(title).strip()
    description = "" if description is None else str(description).strip()

    if title and description:
        return f"Summary: {title}\nDescription: {description}"
    if title:
        return f"Summary: {title}"
    if description:
        return f"Description: {description}"
    return ""