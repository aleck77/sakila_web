# config.py
import os

MYSQL_CONFIG = {
    "host": os.getenv("MYSQL_HOST", "localhost"),
    "port": int(os.getenv("MYSQL_PORT", "3306")),
    "user": os.getenv("MYSQL_USER", "sakila_user"),
    "password": os.getenv("MYSQL_PASSWORD", ""),
    "database": os.getenv("MYSQL_DB", "sakila"),
    "charset": "utf8mb4",
}

MONGO_CONFIG = {
    "uri": os.getenv("MONGO_URI", "mongodb://localhost:27017"),
    "database": os.getenv("MONGO_DB", "logs"),
    "collection": os.getenv("MONGO_COLLECTION", "film_search_logs"),
}