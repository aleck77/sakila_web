"""
Модуль подключения к MongoDB.
"""

from typing import Any
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure, ServerSelectionTimeoutError

from config import MONGO_CONFIG


class MongoDBConnector:
    """Обёртка над MongoClient для работы с коллекцией логов."""

    def __init__(self) -> None:
        self.client: MongoClient | None = None
        self.db: Any = None
        self.collection: Any = None

    def connect(self) -> bool:
        """Подключается к MongoDB и подготавливает коллекцию."""
        try:
            self.client = MongoClient(
                MONGO_CONFIG["uri"],
                serverSelectionTimeoutMS=5000,
            )
            # Проверка подключения
            self.client.admin.command("ping")

            self.db = self.client[MONGO_CONFIG["database"]]
            self.collection = self.db[MONGO_CONFIG["collection"]]
            return True
        except (ConnectionFailure, ServerSelectionTimeoutError) as exc:
            print(f"Ошибка подключения к MongoDB: {exc}")
            self.client = None
            self.db = None
            self.collection = None
            return False

    def disconnect(self) -> None:
        """Закрывает соединение с MongoDB."""
        if self.client is not None:
            self.client.close()
            self.client = None

    def get_collection(self):
        """Возвращает коллекцию MongoDB для работы в других модулях."""
        if self.collection is None:
            raise RuntimeError("Подключение к MongoDB ещё не выполнено.")
        return self.collection
