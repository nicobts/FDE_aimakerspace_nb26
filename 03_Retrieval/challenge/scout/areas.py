# Every query carries the word "coffee" so OpenAlex relevance ranking cannot drift
# into unrelated roasting, packaging or fermentation literature.
# Categories follow schema.Category; the three areas the schema has no value for
# (extraction, packaging, sensory) fall into "other", as use_case/axis_assumptions.md notes.
AREAS: dict[str, dict] = {
    "roasting": {
        "label": "Roasting and coffee chemistry",
        "query": "coffee roasting OR roasted coffee chemistry",
        "category": "roasting",
    },
    "processing": {
        "label": "Green coffee processing and fermentation",
        "query": "green coffee processing OR coffee fermentation",
        "category": "processing",
    },
    "sustainability": {
        "label": "Sustainability and certification",
        "query": "coffee sustainability OR coffee certification",
        "category": "sustainability",
    },
    "agronomy": {
        "label": "Agronomy, varieties and climate",
        "query": "coffee agronomy OR coffee varieties OR coffee climate change",
        "category": "agronomy",
    },
    "extraction": {
        "label": "Extraction and brewing",
        "query": "coffee extraction OR coffee brewing",
        "category": "other",
    },
    "health": {
        "label": "Health and nutrition",
        "query": "coffee health OR coffee consumption nutrition",
        "category": "health",
    },
    "packaging": {
        "label": "Packaging and shelf life",
        "query": "coffee packaging OR coffee shelf life",
        "category": "other",
    },
    "sensory": {
        "label": "Sensory and consumer",
        "query": "coffee sensory OR coffee consumer preference",
        "category": "other",
    },
}
