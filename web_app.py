# web_app.py
from dotenv import load_dotenv
load_dotenv()   # читает .env автоматически при каждом запуске
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, Query, Request
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware

from mysql_connector import MySQLConnector
from mongo_connector import MongoDBConnector
from log_writer import LogWriter
from log_stats import LogStats

app = FastAPI(title="Sakila Film Search Web")

# Простая CORS-настройка (по мере необходимости)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # в проде лучше сузить до своего домена
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------- Инициализация сервисов ----------

@asynccontextmanager
async def lifespan(app: FastAPI):
    # ── СТАРТ ──
    mysql = MySQLConnector()
    if not mysql.connect():
        raise RuntimeError("Cannot connect to MySQL")

    mongo = MongoDBConnector()
    if not mongo.connect():
        mysql.disconnect()
        raise RuntimeError("Cannot connect to MongoDB")

    collection = mongo.get_collection()
    app.state.mysql      = mysql
    app.state.mongo      = mongo
    app.state.log_writer = LogWriter(mongo)
    app.state.log_stats  = LogStats(mongo)

    yield   # ← приложение работает здесь

    # ── СТОП ──
    app.state.mysql.disconnect()
    app.state.mongo.disconnect()


app = FastAPI(title="Sakila Film Search", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------- Dependency ----------

def get_services(request: Request):
    return {
        "mysql":      request.app.state.mysql,
        "log_writer": request.app.state.log_writer,
        "log_stats":  request.app.state.log_stats,
    }

# ---------- Простая HTML-страница ----------

HTML_INDEX = """
<!doctype html>
<html lang="ru">
<head>
  <meta charset="utf-8" />
  <title>Sakila Film Search</title>
</head>
<body>
  <h1>Поиск фильмов Sakila</h1>

  <h2>Поиск по ключевому слову</h2>
  <form action="/api/search/keyword" method="get">
    <input type="text" name="q" placeholder="часть названия" />
    <input type="number" name="page" value="1" min="1" />
    <button type="submit">Искать</button>
  </form>

  <h2>Поиск по жанру и годам</h2>
  <form action="/api/search/genre-years" method="get">
    <label>category_id: <input type="number" name="category_id" /></label><br/>
    <label>year_from: <input type="number" name="year_from" /></label><br/>
    <label>year_to: <input type="number" name="year_to" /></label><br/>
    <label>page: <input type="number" name="page" value="1" min="1" /></label>
    <button type="submit">Искать</button>
  </form>

  <h2>Поиск по рейтингу</h2>
  <form action="/api/search/rating" method="get">
    <input type="text" name="rating" placeholder="PG, PG-13 ..." />
    <input type="number" name="page" value="1" min="1" />
    <button type="submit">Искать</button>
  </form>

  <h2>Статистика</h2>
  <ul>
    <li><a href="/api/stats/top-keywords">Топ ключевых запросов</a></li>
    <li><a href="/api/stats/top-genres">Топ жанров/диапазонов</a></li>
    <li><a href="/api/stats/recent">Последние запросы</a></li>
  </ul>
</body>
</html>
"""

@app.get("/", response_class=HTMLResponse)
async def index():
    return HTML_INDEX

RESULTS_PER_PAGE = 10

# ---------- API-эндпоинты поиска ----------

@app.get("/api/search/keyword")
async def search_by_keyword(
    q: str = Query(..., min_length=1),
    page: int = Query(1, ge=1),
    svc=Depends(get_services),
):
    mysql = svc["mysql"]
    log_writer = svc["log_writer"]

    total = mysql.count_by_keyword(q)
    offset = (page - 1) * RESULTS_PER_PAGE
    films = mysql.search_by_keyword(q, RESULTS_PER_PAGE, offset)

    # логируем один раз на запрос страницы
    log_writer.log_search(
        "keyword",
        {"keyword": q, "page": page},
        len(films),
    )

    return {
        "query": q,
        "page": page,
        "page_size": RESULTS_PER_PAGE,
        "total_found": total,
        "films": films,
    }


@app.get("/api/search/genre-years")
async def search_by_genre_years(
    category_id: int,
    year_from: int,
    year_to: int,
    page: int = Query(1, ge=1),
    svc=Depends(get_services),
):
    mysql = svc["mysql"]
    log_writer = svc["log_writer"]

    total = mysql.count_by_genre_and_years(category_id, year_from, year_to)
    offset = (page - 1) * RESULTS_PER_PAGE
    films = mysql.search_by_genre_and_years(
        category_id, year_from, year_to, RESULTS_PER_PAGE, offset
    )

    log_writer.log_search(
        "genre_years",
        {
            "category_id": category_id,
            "year_from": year_from,
            "year_to": year_to,
            "page": page,
        },
        len(films),
    )

    return {
        "category_id": category_id,
        "year_from": year_from,
        "year_to": year_to,
        "page": page,
        "page_size": RESULTS_PER_PAGE,
        "total_found": total,
        "films": films,
    }


@app.get("/api/search/rating")
async def search_by_rating(
    rating: str,
    page: int = Query(1, ge=1),
    svc=Depends(get_services),
):
    mysql = svc["mysql"]
    log_writer = svc["log_writer"]

    total = mysql.count_by_rating(rating)
    offset = (page - 1) * RESULTS_PER_PAGE
    films = mysql.search_by_rating(rating, RESULTS_PER_PAGE, offset)

    log_writer.log_search(
        "rating",
        {"rating": rating, "page": page},
        len(films),
    )

    return {
        "rating": rating,
        "page": page,
        "page_size": RESULTS_PER_PAGE,
        "total_found": total,
        "films": films,
    }

# ---------- API-эндпоинты статистики ----------

@app.get("/api/stats/top-keywords")
async def top_keywords(limit: int = 5, svc=Depends(get_services)):
    stats = svc["log_stats"].get_top_keyword_searches(limit)
    return {"limit": limit, "items": stats}


@app.get("/api/stats/top-genres")
async def top_genres(limit: int = 5, svc=Depends(get_services)):
    stats = svc["log_stats"].get_top_genre_searches(limit)
    return {"limit": limit, "items": stats}


@app.get("/api/stats/recent")
async def recent_searches(limit: int = 5, svc=Depends(get_services)):
    stats = svc["log_stats"].get_recent_searches(limit)
    return {"limit": limit, "items": stats}