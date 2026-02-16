"""Text alignment and verification utility.

 inspired by Google's langextract library.
Provides functionality to verify if extracted text spans actually exist
in the source document, calculating alignment quality and precise character offsets.
"""

from __future__ import annotations

import difflib
from dataclasses import dataclass
from enum import Enum


class AlignmentStatus(Enum):
    """Quality of the alignment between extraction and source text."""

    EXACT = "exact"       # Perfect character-for-character match
    FUZZY = "fuzzy"       # High similarity match (e.g. minor whitespace/punct diffs)
    PARTIAL = "partial"   # Substring match
    MISSING = "missing"   # No confident match found


@dataclass
class AlignmentResult:
    """Result of aligning text against a source document."""

    status: AlignmentStatus
    start_char: int
    end_char: int
    matched_text: str
    similarity_score: float  # 0.0 to 1.0


class TextAligner:
    """Aligns extracted text snippets to source document context."""

    def __init__(self, fuzzy_threshold: float = 0.8):
        """Initialize aligner.

        Args:
            fuzzy_threshold: Minimum similarity score (0-1) to accept a fuzzy match.
        """
        self.fuzzy_threshold = fuzzy_threshold

    def align(self, snippet: str, source_text: str) -> AlignmentResult:
        """Find the best match for snippet in source_text.

        Returns:
            AlignmentResult with status and position indices.
        """
        if not snippet or not source_text:
            return AlignmentResult(
                AlignmentStatus.MISSING, -1, -1, "", 0.0
            )

        # 1. Try exact match first (fastest)
        start_idx = source_text.find(snippet)
        if start_idx != -1:
            return AlignmentResult(
                status=AlignmentStatus.EXACT,
                start_char=start_idx,
                end_char=start_idx + len(snippet),
                matched_text=snippet,
                similarity_score=1.0,
            )

        # 2. Try normalized exact match (ignore case/whitespace)
        # This is strictly for finding the location; we return indices into original source_text
        snippet_norm = " ".join(snippet.lower().split())
        source_norm = " ".join(source_text.lower().split())

        # Note: mapping normalized indices back to original is hard.
        # Instead, we'll use difflib for robust fuzzy matching if exact fails.

        # 3. Fuzzy match using SequenceMatcher
        matcher = difflib.SequenceMatcher(None, source_text, snippet, autojunk=False)
        match = matcher.find_longest_match(0, len(source_text), 0, len(snippet))

        # Check if the longest match is substantial enough
        if match.size > 0:
            # Get the substring from source that corresponds to the match
            # We assume the matching part is the "core" of the snippet
            candidate_start = match.a
            candidate_end = match.a + match.size
            candidate_text = source_text[candidate_start:candidate_end]

            # Calculate similarity between full snippet and the candidate region
            # We expand the region slightly to see if we can cover the whole snippet?
            # Creating a true fuzzy find is expensive.
            # Simplified approach: Use the longest common substring as anchor.

            similarity = match.size / len(snippet)

            if similarity >= 0.99: # Practically exact but maybe some edge case
                 return AlignmentResult(
                    AlignmentStatus.EXACT, candidate_start, candidate_end, candidate_text, similarity
                )
            elif similarity >= self.fuzzy_threshold:
                return AlignmentResult(
                    AlignmentStatus.FUZZY, candidate_start, candidate_end, candidate_text, similarity
                )
            elif similarity > 0.5:
                return AlignmentResult(
                    AlignmentStatus.PARTIAL, candidate_start, candidate_end, candidate_text, similarity
                )

        return AlignmentResult(
            AlignmentStatus.MISSING, -1, -1, "", 0.0
        )
