"""Conservative typo normalization for terms supported by the P3 corpora."""

from __future__ import annotations

from difflib import get_close_matches
import re


def normalize_query(query: str, vocabulary: tuple[str, ...]) -> str:
    """Correct only close misspellings of known corpus terms.

    This deliberately does not attempt open-ended spell correction. It prevents a
    typo in a supported topic from hiding available evidence while preserving the
    user's wording for unrelated terms.
    """

    normalized_vocabulary = {term.lower() for term in vocabulary}

    def replace(match: re.Match[str]) -> str:
        token = match.group(0)
        lowered = token.lower()
        if lowered in normalized_vocabulary or len(lowered) < 4:
            return token
        matches = get_close_matches(lowered, normalized_vocabulary, n=1, cutoff=0.84)
        return matches[0] if matches else token

    return re.sub(r"[A-Za-z]+", replace, query)
