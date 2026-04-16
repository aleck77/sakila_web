"""
Модуль для получения статистики поисковых запросов из MongoDB.
"""

from typing import Any, Dict, List

class LogStats:
    """Агрегации по коллекции логов в MongoDB."""

    def __init__(self, mongo_connector) -> None:
        self.collection = mongo_connector.get_collection()

    def get_top_keyword_searches(self, limit: int = 5) -> List[Dict[str, Any]]:
        """
        Топ популярных запросов по ключевому слову.
        Группировка по params.keyword.
        """
        pipeline = [
            {"$match": {"search_type": "keyword"}},
            {
                "$group": {
                    "_id": "$params.keyword",
                    "count": {"$sum": 1},
                    "last_search": {"$max": "$timestamp"},
                }
            },
            {"$sort": {"count": -1, "last_search": -1}},
            {"$limit": limit},
        ]
        results = list(self.collection.aggregate(pipeline))
        return [
            {
                "keyword": item["_id"],
                "count": item["count"],
                "last_search": item["last_search"],
            }
            for item in results
        ]

    def get_top_genre_searches(self, limit: int = 5) -> List[Dict[str, Any]]:
        """
        Топ популярных запросов по жанру и диапазону лет.
        """
        pipeline = [
            {"$match": {"search_type": "genre_years"}},
            {
                "$group": {
                    "_id": {
                        "category": "$params.category_name",
                        "years": {
                            "from": "$params.year_from",
                            "to": "$params.year_to",
                        },
                    },
                    "count": {"$sum": 1},
                    "last_search": {"$max": "$timestamp"},
                }
            },
            {"$sort": {"count": -1, "last_search": -1}},
            {"$limit": limit},
        ]
        results = list(self.collection.aggregate(pipeline))
        # return [
        #     {
        #         "category": item["_id"]["category"],
        #         "years": f"{item['_id']['years']['from']}-{item['_id']['years']['to']}",
        #         "count": item["count"],
        #         "last_search": item["last_search"],
        #     }
        #     for item in results
        # ]
        return [
            {
                "category": item.get("_id", {}).get("category", "Неизвестный жанр"),
                "years": f"{item.get('_id', {}).get('years_from', 'N/A')}-{item.get('_id', {}).get('years_to', 'N/A')}",
                "count": item.get("count", 0),
                "last_search": item.get("last_search"),
            }
            for item in results
        ]

    def get_recent_searches(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Последние N поисковых запросов по времени.
        """
        cursor = (
            self.collection.find()
            .sort("timestamp", -1)
            .limit(limit)
        )
        results: List[Dict[str, Any]] = []
        for doc in cursor:
            entry: Dict[str, Any] = {
                "timestamp": doc.get("timestamp"),
                "type": doc.get("search_type"),
                "results_count": doc.get("results_count", 0),
            }
            params = doc.get("params", {})
            if doc.get("search_type") == "keyword":
                entry["query"] = f"Keyword: {params.get('keyword')}"
            # elif doc.get("search_type") == "genre_years":
            #     entry["query"] = (
            #         f"Genre: {params.get('category_name')}, "
            #         f"Years: {params.get('year_from')}-{params.get('year_to')}"
            #     )
            elif doc.get("search_type") == "genre_years":
                cat_name = params.get('category_name') or f"ID:{params.get('category_id', '?')}"
                entry["query"] = f"Жанр: {cat_name}, Года: {params.get('year_from')}-{params.get('year_to')}"

            elif doc.get("search_type") == "rating":
                entry["query"] = f"Rating: {params.get('rating')}"
            else:
                entry["query"] = str(params)

            results.append(entry)
        return results
