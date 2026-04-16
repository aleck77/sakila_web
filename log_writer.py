"""
Модуль для записи поисковых запросов в MongoDB.
"""

from datetime import datetime
from typing import Any, Dict

class LogWriter:
    """Логирование поисковых запросов в коллекцию MongoDB."""

    def __init__(self, mongo_connector) -> None:
        self.collection = mongo_connector.get_collection()

    def log_search(
        self,
        search_type: str,
        params: Dict[str, Any],
        results_count: int,
    ) -> None:
        """
        Записывает документ лога в коллекцию.

        search_type: 'keyword', 'genre_years', 'rating', ...
        params: словарь с параметрами поиска
        results_count: сколько фильмов найдено
        """
        doc = {
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "search_type": search_type,
            "params": params,
            "results_count": results_count,
        }
        try:
            self.collection.insert_one(doc)
        except Exception as exc:  # noqa: BLE001
            # Логирование ошибок
            print(f"Ошибка записи лога в MongoDB: {exc}")
