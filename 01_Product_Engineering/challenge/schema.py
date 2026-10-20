"""The contract for one document in, one article card out.

Later weeks build on this shape: the sweep calls it once per document it
fetches, the store keeps the cards, the weekly report rolls them up.
"""

from typing import Literal

from pydantic import BaseModel, Field

Language = Literal["en", "it"]

Category = Literal[
    "agronomy",
    "processing",
    "roasting",
    "health",
    "sustainability",
    "other",
]

TrustLevel = Literal["high", "medium", "low"]

TrustWarning = Literal[
    "not_peer_reviewed",
    "small_sample",
    "methods_not_described",
    "no_controls",
    # Added in TC2. The R&D team said these are the problems a reader misses
    # most easily, because the study otherwise looks sound.
    "lab_scale_only",
    "in_vitro_or_animal_only",
    "industry_funded",
    "single_origin_or_batch",
    "no_statistics",
    "abstract_only",
]

# Who produced the study. An independent university result and a supplier's own
# trial can report the same number and deserve different trust.
Affiliation = Literal[
    "university_or_public_institute",
    "company",
    "mixed",
    "unknown",
]

TRUST_RULES = (
    "high: peer-reviewed, controlled, adequate sample, statistics reported, and "
    "conditions close to industrial practice or to humans; at most one minor warning. "
    "medium: sound but limited, with one or two warnings, for example lab_scale_only "
    "or single_origin_or_batch. "
    "low: three or more warnings, or any of not_peer_reviewed together with "
    "industry_funded, or in_vitro_or_animal_only when the claim is about people, "
    "or small_sample in a pilot study that makes a health claim."
)


class Request(BaseModel):
    document_text: str = Field(
        description="The paper, abstract or article text, in English"
    )
    title: str | None = Field(default=None, description="Title, if known")
    source: str | None = Field(
        default=None,
        description="Where it was published: journal, site or preprint server",
    )
    focus: str | None = Field(
        default=None,
        description="The topic or question the reader is deciding on, if any",
    )
    output_languages: list[Language] = Field(
        default=["en", "it"],
        description="Languages to write the summary and notes in",
    )


class Response(BaseModel):
    # No default: the model must always say whether it is declining.
    needs_human: bool = Field(
        description="True when the text cannot be summarised reliably and a "
        "researcher should read it instead"
    )
    needs_human_reason: str | None = Field(
        default=None, description="Why it was declined; set when needs_human is True"
    )

    # Written once and never translated, so the two summaries cannot disagree.
    category: Category | None = Field(
        default=None, description="The research area the document belongs to"
    )
    relevance: int | None = Field(
        default=None,
        ge=1,
        le=3,
        description="1 = background, 2 = worth reading, 3 = act on it; judged "
        "against focus when one is given",
    )
    study_type: str | None = Field(
        default=None,
        description="For example: field trial, lab experiment, review, survey",
    )
    sample_size: int | None = Field(
        default=None, description="Number of samples or participants, if stated"
    )
    main_finding: str | None = Field(
        default=None, description="The central result in one sentence, in English"
    )

    summary_en: str | None = Field(
        default=None, description="Summary in English; None if not requested"
    )
    summary_it: str | None = Field(
        default=None, description="Summary in Italian; None if not requested"
    )
    notes_en: str | None = Field(
        default=None,
        description="What the reader should check or do next, in English",
    )
    notes_it: str | None = Field(
        default=None,
        description="What the reader should check or do next, in Italian",
    )

    # Kept apart from needs_human: a weak study still gets a card, with a caveat.
    affiliation: Affiliation | None = Field(
        default=None,
        description="Who produced the study, as far as the text shows; unknown "
        "when it does not say",
    )
    trust_level: TrustLevel | None = Field(
        default=None,
        description="How far the study can be relied on. " + TRUST_RULES,
    )
    trust_warnings: list[TrustWarning] = Field(
        default_factory=list,
        description="The warning signs found that explain the trust level. "
        "industry_funded applies when funding or authorship comes from a company "
        "with a commercial interest in the result; abstract_only when only the "
        "abstract is available, so methods cannot be checked",
    )


def solve(request: Request) -> Response:
    """Turn one document into an article card.

    Declines with needs_human=True instead of guessing when the text is not a
    study, is too short to judge, or is not about coffee.
    """
    raise NotImplementedError("implement against this signature")
