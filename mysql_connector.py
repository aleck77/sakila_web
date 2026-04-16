"""
Модуль для работы с MySQL-базой данных sakila.
"""

from typing import List, Dict, Tuple
import pymysql
from pymysql.cursors import DictCursor

from config import MYSQL_CONFIG


class MySQLConnector:
    """Класс-обёртка над соединением с MySQL (sakila)."""

    def __init__(self) -> None:
        self.connection: pymysql.Connection | None = None

    def connect(self) -> bool:
        """Устанавливает соединение с MySQL. Возвращает True при успехе."""
        try:
            self.connection = pymysql.connect(
                cursorclass=DictCursor,
                **MYSQL_CONFIG,
            )
            return True
        except pymysql.Error as exc:
            print(f"Ошибка подключения к MySQL: {exc}")
            self.connection = None
            return False

    def disconnect(self) -> None:
        """Закрывает соединение с MySQL."""
        if self.connection is not None:
            self.connection.close()
            self.connection = None

    def _cursor(self) -> DictCursor:
        if self.connection is None:
            raise RuntimeError("Соединение с MySQL не установлено.")
        return self.connection.cursor()

    # ---------- Справочная информация ----------

    def get_all_categories(self) -> List[Dict]:
        """
        Возвращает список жанров (category_id, name), отсортированных по имени.
        """
        query = "SELECT category_id, name FROM category ORDER BY name"
        with self._cursor() as cursor:
            cursor.execute(query)
            return cursor.fetchall()

    def get_year_range(self) -> Tuple[int, int]:
        """
        Возвращает минимальный и максимальный годы выпуска фильмов.
        """
        query = (
            "SELECT MIN(release_year) AS min_year, "
            "MAX(release_year) AS max_year FROM film"
        )
        with self._cursor() as cursor:
            cursor.execute(query)
            row = cursor.fetchone()
            return int(row["min_year"]), int(row["max_year"])

    def get_all_ratings(self) -> List[str]:
        """
        Возвращает отсортированный список доступных рейтингов (строки).
        """
        query = (
            "SELECT DISTINCT rating FROM film "
            "WHERE rating IS NOT NULL "
            "ORDER BY rating"
        )
        with self._cursor() as cursor:
            cursor.execute(query)
            return [row["rating"] for row in cursor.fetchall()]

    # ---------- Поиск по ключевому слову ----------

    def count_by_keyword(self, keyword: str) -> int:
        """Возвращает количество фильмов, где title LIKE %keyword%."""
        query = "SELECT COUNT(*) AS cnt FROM film WHERE title LIKE %s"
        with self._cursor() as cursor:
            cursor.execute(query, (f"%{keyword}%",))
            row = cursor.fetchone()
            return int(row["cnt"])

    def search_by_keyword(
        self, keyword: str, limit: int = 10, offset: int = 0
    ) -> List[Dict]:
        """
        Возвращает список фильмов, отфильтрованных по title LIKE %keyword%.
        Используется пагинация через LIMIT/OFFSET.
        """
        query = """
            SELECT
                f.film_id,
                f.title,
                f.description,
                f.release_year,
                f.rating,
                f.length,
                f.rental_rate,
                l.name AS language
            FROM film AS f
                LEFT JOIN language AS l
                    ON f.language_id = l.language_id
            WHERE f.title LIKE %s
            ORDER BY f.title
            LIMIT %s OFFSET %s
        """
        with self._cursor() as cursor:
            cursor.execute(query, (f"%{keyword}%", limit, offset))
            return cursor.fetchall()

    # ---------- Поиск по жанру и диапазону годов ----------

    def count_by_genre_and_years(
        self,
        category_id: int,
        year_from: int,
        year_to: int,
    ) -> int:
        query = """
            SELECT COUNT(*) AS cnt
            FROM film AS f
                INNER JOIN film_category AS fc
                    ON f.film_id = fc.film_id
            WHERE fc.category_id = %s
              AND f.release_year BETWEEN %s AND %s
        """
        with self._cursor() as cursor:
            cursor.execute(query, (category_id, year_from, year_to))
            row = cursor.fetchone()
            return int(row["cnt"])

    def search_by_genre_and_years(
        self,
        category_id: int,
        year_from: int,
        year_to: int,
        limit: int = 10,
        offset: int = 0,
    ) -> List[Dict]:
        """
        Возвращает фильмы указанного жанра в заданном диапазоне лет.
        """
        query = """
            SELECT
                f.film_id,
                f.title,
                f.description,
                f.release_year,
                f.rating,
                f.length,
                f.rental_rate,
                l.name AS language,
                c.name AS category
            FROM film AS f
                LEFT JOIN language AS l
                    ON f.language_id = l.language_id
                INNER JOIN film_category AS fc
                    ON f.film_id = fc.film_id
                INNER JOIN category AS c
                    ON fc.category_id = c.category_id
            WHERE c.category_id = %s
              AND f.release_year BETWEEN %s AND %s
            ORDER BY f.release_year DESC, f.title
            LIMIT %s OFFSET %s
        """
        with self._cursor() as cursor:
            cursor.execute(
                query,
                (category_id, year_from, year_to, limit, offset),
            )
            return cursor.fetchall()

    # ---------- Поиск по рейтингу ----------

    def count_by_rating(self, rating: str) -> int:
        query = "SELECT COUNT(*) AS cnt FROM film WHERE rating = %s"
        with self._cursor() as cursor:
            cursor.execute(query, (rating,))
            row = cursor.fetchone()
            return int(row["cnt"])

    def search_by_rating(
        self, rating: str, limit: int = 10, offset: int = 0
    ) -> List[Dict]:
        query = """
            SELECT
                f.film_id,
                f.title,
                f.description,
                f.release_year,
                f.rating,
                f.length,
                f.rental_rate,
                l.name AS language
            FROM film AS f
                LEFT JOIN language AS l
                    ON f.language_id = l.language_id
            WHERE f.rating = %s
            ORDER BY f.title
            LIMIT %s OFFSET %s
        """
        with self._cursor() as cursor:
            cursor.execute(query, (rating, limit, offset))
            return cursor.fetchall()
