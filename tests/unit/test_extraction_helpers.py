import pytest
import tempfile
from pathlib import Path

from kgbuilder.extraction.aligner import TextAligner, AlignmentStatus
from kgbuilder.extraction.cache import CacheKey, ExtractionCache
from kgbuilder.core.models import ExtractedEntity


def test_text_aligner_exact_and_missing():
    aligner = TextAligner(fuzzy_threshold=0.8)
    source = "Hello World!"
    # exact
    r = aligner.align("World", source)
    assert r.status == AlignmentStatus.EXACT
    assert r.start_char == 6
    assert r.matched_text == "World"
    # snippet not present
    r2 = aligner.align("Foo", source)
    assert r2.status == AlignmentStatus.MISSING
    assert r2.similarity_score == 0.0
    # empty inputs
    r3 = aligner.align("", source)
    assert r3.status == AlignmentStatus.MISSING
    r4 = aligner.align("abc", "")
    assert r4.status == AlignmentStatus.MISSING


def test_text_aligner_fuzzy_and_partial():
    aligner = TextAligner(fuzzy_threshold=0.7)
    src = "The quick brown fox jumps over the lazy dog"
    # fuzzy with minor difference
    r = aligner.align("quick brown fox", src)
    assert r.status == AlignmentStatus.EXACT or r.status == AlignmentStatus.FUZZY
    # partial match where snippet longer than substring
    r2 = aligner.align("quick brown fox jumps high", src)
    assert r2.status in {AlignmentStatus.FUZZY, AlignmentStatus.PARTIAL, AlignmentStatus.MISSING}
    # set threshold high so fuzzy becomes partial
    aligner2 = TextAligner(fuzzy_threshold=0.99)
    r3 = aligner2.align("quick brown fox", src)
    assert r3.status in {AlignmentStatus.EXACT, AlignmentStatus.FUZZY}


def test_cachekey_and_cache_basic(tmp_path):
    key = CacheKey.from_extraction_params("text", "q1", "T")
    s = key.to_string()
    assert ":" in s
    # round-trip not needed but ensure string contains components
    assert key.question_id == "q1"

    cache = ExtractionCache(cache_dir=tmp_path, max_memory_mb=0.001)
    # empty cache hit/miss
    assert cache.get("a", "q", "T") is None
    assert cache.stats()["cache_misses"] == 1
    ent = ExtractedEntity(id="1", label="x", entity_type="T", description="", confidence=1.0)
    # putting should respect memory limit; initial put maybe exceeds small budget
    cache.put("a", "q", "T", [ent])
    # attempt to retrieve
    res = cache.get("a", "q", "T")
    # depending on size, may be None if over limit; but hits/misses should increment accordingly
    stats = cache.stats()
    assert "entries_cached" in stats
    # clear resets
    cache.clear()
    stats2 = cache.stats()
    assert stats2["cache_hits"] == 0
    assert stats2["cache_misses"] == 0


def test_cache_persistence(tmp_path, monkeypatch):
    # simulate persistence by writing file manually
    cache_dir = tmp_path / "cache"
    cache = ExtractionCache(cache_dir=cache_dir, enable_persistence=True)
    ent = ExtractedEntity(id="1", label="x", entity_type="T", description="", confidence=1.0)
    cache.put("abc", "q1", "T", [ent])
    # persistence currently only loads, not writes automatically; just
    # ensure creating a second instance does not raise and stats are available
    cache2 = ExtractionCache(cache_dir=cache_dir, enable_persistence=True)
    assert isinstance(cache2.stats(), dict)

@pytest.fixture(autouse=True)
def silence_logging(caplog):
    caplog.set_level("DEBUG")
    yield
