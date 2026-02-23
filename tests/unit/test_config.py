from pathlib import Path

from kgbuilder.core.config import ProcessingConfig


def test_processing_config_defaults(tmp_path):
    # override default dirs to temp_path
    cache = tmp_path / "cache"
    temp = tmp_path / "temp"
    cfg = ProcessingConfig(cache_dir=cache, temp_dir=temp)
    # directories should be created
    assert cache.is_dir()
    assert temp.is_dir()
    # default flags
    assert not cfg.enable_vlm
    assert cfg.enable_caching
    assert cfg.chunk_size == 1024


def test_processing_config_custom_values(tmp_path):
    cache = tmp_path / "c2"
    temp = tmp_path / "t2"
    cfg = ProcessingConfig(
        enable_vlm=True,
        enable_ocr=True,
        cache_dir=cache,
        temp_dir=temp,
        chunk_size=512,
        max_workers=10,
    )
    assert cfg.enable_vlm
    assert cfg.enable_ocr
    assert cfg.chunk_size == 512
    assert cfg.max_workers == 10
