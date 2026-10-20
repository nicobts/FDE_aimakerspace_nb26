"""Variation axes for the TC2 synthetic dataset.

Each value is pasted into the generation prompt as plain text, so it has to be a
description the model can act on, not a label. The variation they cover comes
from use_case/axis_assumptions.md. The datasheet's axes table must match this file.
"""

# Kept apart from AXES so the generator never sees them; the datasheet copies them.
REASONS: dict[str, str] = {
    "text_type": "What lands on the desk: abstracts dominate, but full text, preprints and "
    "supplier notes also arrive, and four of five goldens are abstracts only.",
    "research_area": "Roasting and processing are the most frequent requests; packaging is "
    "frequent too but has no schema category, so it tests whether 'other' is used honestly.",
    "outcome": "A card, a card with a visible caveat, a card whose weakness is easy to "
    "miss, or a decline. The two declines are the hard ones from the assumptions, not "
    "'not about coffee', which golden 5 already covers.",
}

AXES: dict[str, list[str]] = {
    "text_type": [
        "an English abstract of 150-250 words from a peer-reviewed food science or "
        "agronomy journal, with background, methods and results",
        "a 600-900 word excerpt of a peer-reviewed paper's methods and results sections, "
        "with numbers, units and statistical tests",
        "a preprint abstract that is not yet peer-reviewed, with a bold claim in the title",
        "a 300-500 word technical note from a coffee equipment or ingredient supplier, "
        "citing one internal trial and partly written as marketing",
    ],
    "research_area": [
        "roasting chemistry: aroma compounds, acrylamide or chlorogenic acids across "
        "roast profiles",
        "green coffee processing: fermentation, washed versus natural, or drying at farm "
        "or wet-mill level",
        "packaging and shelf life of roasted coffee or capsules: oxygen barriers, "
        "degassing, staling; the schema has no category for it, so it belongs in 'other'",
    ],
    "outcome": [
        "a solid study with clear methods, an adequate sample and controls; a card with "
        "high trust",
        "a visibly weak study: small sample, no controls, no statistics or vague "
        "methods; a card with low or medium trust and the matching warnings",
        "a study that reads as sound but is weak in a way that is easy to miss: "
        "lab-scale roaster or pilot conditions far from industrial practice, cell or "
        "animal results presented as applying to people, a single origin or batch "
        "generalised to all coffee, or funded by a company selling the product; a "
        "card with medium or low trust and the matching warnings",
        "coffee is mentioned only in passing, for example caffeine intake as one "
        "covariate in a sleep study; the system should decline with needs_human",
        "the text is cut off mid-sentence or under 60 words, too short to judge; the "
        "system should decline with needs_human",
    ],
}

# Substrings that mark a value as a decline. Week 4 needs declines to measure
# calibration, so the check below refuses to pass without one.
DECLINE_MARKERS = ("decline", "needs_human")


if __name__ == "__main__":
    from math import prod

    missing = set(AXES) - set(REASONS)
    assert not missing, f"axes with no reason: {missing}"
    has_decline = any(
        marker in value.lower()
        for values in AXES.values()
        for value in values
        for marker in DECLINE_MARKERS
    )
    assert has_decline, "no axis value says the system should decline"
    combos = prod(len(values) for values in AXES.values())
    print(f"{len(AXES)} axes, {combos} combinations")
    assert combos <= 60, "too many combinations for the time left; cut values"
