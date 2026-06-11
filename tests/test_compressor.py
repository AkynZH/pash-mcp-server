# -*- coding: utf-8 -*-
import pytest
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.compressor import AdaptivePashCompressor

def test_compress_large_json_saves_tokens():
    """Проверка, что большие JSON-ответы эффективно сжимаются (>50% экономии)."""
    compressor = AdaptivePashCompressor(min_size_threshold=100)
    
    # Создаем "тяжелый" ответ с повторяющимися ключами
    raw_data = {
        "results": [
            {"name": f"Item_{i}", "description": "Test desc", "url": "http://example.com", "status": "ok"}
            for i in range(20)
        ]
    }
    
    result = compressor.compress(raw_data)
    
    assert result["compressed"] is True
    assert "raw_hash" in result
    assert "pash" in result
    
    # Проверяем, что сжатые данные содержат унифицированные значения
    pash = result["pash"]
    assert "_u" in pash["res"]  # 'results' сжимается до 'res'
    
    # Проверяем экономию размера (грубая оценка)
    import json
    raw_len = len(json.dumps(raw_data, ensure_ascii=False))
    pash_len = len(json.dumps(pash, ensure_ascii=False))
    
    assert pash_len < raw_len * 0.5, f"Сжатие недостаточно эффективно: {pash_len} vs {raw_len}"


def test_skip_small_data():
    """Проверка, что малые данные не сжимаются."""
    compressor = AdaptivePashCompressor(min_size_threshold=500)
    raw_data = {"status": "ok", "message": "hi"}
    
    result = compressor.compress(raw_data)
    assert result["compressed"] is False
    assert result["pash"] == raw_data


def test_skip_binary_like_data():
    """Проверка, что бинарные (base64) данные пропускаются."""
    compressor = AdaptivePashCompressor(min_size_threshold=100)
    raw_data = {
        "image": "A" * 1500, # Имитация длинной base64 строки (>1000 символов для триггера эвристики)
        "name": "test"
    }
    
    result = compressor.compress(raw_data)
    assert result["compressed"] is False
    assert result["pash"] == raw_data