# -*- coding: utf-8 -*-
"""
AdaptivePashCompressor v1.0 — Интеллектуальное сжатие ответов MCP перед отправкой LLM.
Применяет PASH-сжатие только к "тяжелым" текстовым/JSON ответам (>500 символов).
Пропускает бинарные данные и малые ответы для минимизации накладных расходов.
"""
import hashlib
import json
import re
from typing import Any, Dict

class AdaptivePashCompressor:
    def __init__(self, min_size_threshold: int = 500):
        self.min_size_threshold = min_size_threshold
        # Маппинг для стандартных сокращений ключей (PASH-словарь)
        self.key_map = {
            "status": "s", "success": "ok", "error": "err",
            "data": "d", "result": "r", "results": "res",
            "name": "n", "full_name": "fn", "description": "desc",
            "url": "u", "source": "src", "title": "t", "summary": "sum",
            "stars": "stars", "forks": "forks", "issues": "issues",
            "language": "lang", "query": "q", "row_count": "c", "rows": "r",
            "items": "i", "path": "p"
        }

    def _is_binary_or_heavy(self, data: Any) -> bool:
        """Проверка на бинарные или строго типизированные данные."""
        if isinstance(data, str):
            # Проверка на base64 или очень длинные строки без структуры
            if re.match(r'^[A-Za-z0-9+/=]{100,}$', data):
                return True
        elif isinstance(data, dict):
            # Проверка на наличие бинарных полей
            for k, v in data.items():
                if isinstance(v, str) and len(v) > 1000 and re.match(r'^[A-Za-z0-9+/=]+$', v):
                    return True
                # Финансовые дроби или точные метки времени (упрощенно: если много float с высокой точностью)
                if isinstance(v, float) and len(str(v).split('.')[1]) > 6:
                    return True
        return False

    def _compress_list(self, v: list) -> Any:
        """Продвинутое сжатие списков словарей: вынос унифицированных значений."""
        if not v or not isinstance(v[0], dict):
            return [self._compress_dict(item) if isinstance(item, dict) else item for item in v]

        keys = list(v[0].keys())
        # Проверяем, что у всех элементов одинаковые ключи в одинаковом порядке
        if not all(list(item.keys()) == keys for item in v):
            return [self._compress_dict(item) for item in v]

        # Поиск унифицированных (постоянных) значений по всем элементам
        uniform_vals = {}
        for key in keys:
            first_val = v[0][key]
            if all(item[key] == first_val for item in v):
                uniform_vals[key] = first_val

        # Если есть унифицированные значения и элементов достаточно для выгоды
        if uniform_vals and len(v) >= 5:
            short_uniform = {self.key_map.get(k, k[:3]): val for k, val in uniform_vals.items()}
            row_keys = [k for k in keys if k not in uniform_vals]

            # Если все ключи унифицированы, возвращаем просто одну запись и счетчик
            if not row_keys:
                return {"_u": short_uniform, "_c": len(v)}

            short_row_keys = [self.key_map.get(k, k[:3]) for k in row_keys]
            rows = [[item[k] for k in row_keys] for item in v]
            return {"_u": short_uniform, "_k": short_row_keys, "_v": rows}
        else:
            # Если элементов мало, выгоднее просто сжать каждый словарь индивидуально,
            # что также гарантирует рекурсивное сжатие вложенных структур (например, JSON-строк).
            return [self._compress_dict(item) if isinstance(item, dict) else item for item in v]

    def _compress_dict(self, d: Dict) -> Dict:
        """Рекурсивное сжатие словаря с заменой ключей и оптимизацией списков."""
        compressed = {}
        for k, v in d.items():
            short_key = self.key_map.get(k, k[:3]) # Если ключа нет в мапе, берем первые 3 символа
            if isinstance(v, dict):
                compressed[short_key] = self._compress_dict(v)
            elif isinstance(v, list):
                compressed[short_key] = self._compress_list(v)
            elif isinstance(v, str):
                # Попытка распарсить и сжать большие JSON-строки (частый кейс для MCP text полей)
                if len(v) > self.min_size_threshold and (v.startswith('{') or v.startswith('[')):
                    try:
                        parsed = json.loads(v)
                        compressed[short_key] = self._compress_dict(parsed) if isinstance(parsed, dict) else self._compress_list(parsed)
                    except json.JSONDecodeError:
                        compressed[short_key] = v
                else:
                    compressed[short_key] = v
            else:
                compressed[short_key] = v
        return compressed

    def compress(self, raw_response: Any) -> Dict[str, Any]:
        """
        Основной метод сжатия.
        Возвращает: {"pash": {...}, "raw_hash": "...", "compressed": bool}
        """
        raw_str = json.dumps(raw_response, ensure_ascii=False, separators=(',', ':')) if not isinstance(raw_response, str) else raw_response

        # 1. Проверка размера
        if len(raw_str) < self.min_size_threshold:
            return {
                "pash": raw_response,
                "raw_hash": hashlib.sha256(raw_str.encode('utf-8')).hexdigest(),
                "compressed": False
            }

        # 2. Проверка на бинарные данные
        if self._is_binary_or_heavy(raw_response):
            return {
                "pash": raw_response,
                "raw_hash": hashlib.sha256(raw_str.encode('utf-8')).hexdigest(),
                "compressed": False
            }

        # 3. Применение PASH-сжатия
        try:
            if isinstance(raw_response, str):
                try:
                    parsed = json.loads(raw_response)
                    compressed_data = self._compress_dict(parsed)
                except json.JSONDecodeError:
                    # Если это не JSON, а просто длинный текст, оставляем как есть
                    compressed_data = raw_response
            else:
                compressed_data = self._compress_dict(raw_response)

            return {
                "pash": compressed_data,
                "raw_hash": hashlib.sha256(raw_str.encode('utf-8')).hexdigest(),
                "compressed": True
            }
        except Exception:
            # В случае ошибки сжатия возвращаем оригинал с флагом false
            return {
                "pash": raw_response,
                "raw_hash": hashlib.sha256(raw_str.encode('utf-8')).hexdigest(),
                "compressed": False
            }