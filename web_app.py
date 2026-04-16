# web_app.py
from pathlib import Path
from dotenv import load_dotenv
load_dotenv()   # читает .env автоматически при каждом запуске
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, Query, Request
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware

from mysql_connector import MySQLConnector
from mongo_connector import MongoDBConnector
from log_writer import LogWriter
from log_stats import LogStats

app = FastAPI(title="Sakila Film Search Web")
BASE_DIR = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))
RESULTS_PER_PAGE = 10

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

# ---------- Главная страница ----------

@app.get("/", response_class=HTMLResponse)
async def index(request: Request, svc=Depends(get_services)):
    mysql = svc["mysql"]
    categories = mysql.get_all_categories()
    year_from, year_to = mysql.get_year_range()
    ratings = mysql.get_all_ratings()
    
    return templates.TemplateResponse(
        request, 
        "index.html", 
        {
            "request": request, 
            "categories": categories,
            "min_year": year_from,
            "max_year": year_to,
            "ratings": ratings
        }
    )

# ---------- API-эндпоинты поиска (теперь возвращают HTML) ----------

@app.get("/api/search/keyword", response_class=HTMLResponse)
async def search_by_keyword(
    request: Request,
    q: str = Query(..., min_length=1),
    page: int = Query(1, ge=1),
    svc=Depends(get_services),
):
    mysql = svc["mysql"]
    log_writer = svc["log_writer"]

    total = mysql.count_by_keyword(q)
    offset = (page - 1) * RESULTS_PER_PAGE
    films = mysql.search_by_keyword(q, RESULTS_PER_PAGE, offset)

    log_writer.log_search("keyword", {"keyword": q, "page": page}, len(films))

    return templates.TemplateResponse(
        request, "index.html",
        {
            "request": request, "films": films, "total_found": total, "page": page,
            "search_type": "keyword", "q": q, "categories": mysql.get_all_categories(),
            "min_year": mysql.get_year_range()[0], "max_year": mysql.get_year_range()[1],
            "ratings": mysql.get_all_ratings()
        }
    )

@app.get("/api/search/genre-years", response_class=HTMLResponse)
async def search_by_genre_years(
    request: Request,
    category_id: int, year_from: int, year_to: int,
    page: int = Query(1, ge=1),
    svc=Depends(get_services),
):
    mysql = svc["mysql"]
    log_writer = svc["log_writer"]

    total = mysql.count_by_genre_and_years(category_id, year_from, year_to)
    offset = (page - 1) * RESULTS_PER_PAGE
    films = mysql.search_by_genre_and_years(category_id, year_from, year_to, RESULTS_PER_PAGE, offset)

    # 1. Находим имя жанра по его ID из списка всех жанров
    categories = mysql.get_all_categories()
    category_name = next((c["name"] for c in categories if c["category_id"] == category_id), str(category_id))
    log_writer.log_search(
        "genre_years", 
        {
            "category_name": category_name, 
            "year_from": year_from, 
            "year_to": year_to, 
            "page": page
        }, 
        len(films))

    return templates.TemplateResponse(
        request, "index.html",
        {
            "request": request, "films": films, "total_found": total, "page": page,
            "search_type": "genre-years", "category_id": category_id, "year_from": year_from, "year_to": year_to,
            "categories": mysql.get_all_categories(), "min_year": mysql.get_year_range()[0], "max_year": mysql.get_year_range()[1],
            "ratings": mysql.get_all_ratings()
        }
    )

@app.get("/api/search/rating", response_class=HTMLResponse)
async def search_by_rating(
    request: Request,
    rating: str,
    page: int = Query(1, ge=1),
    svc=Depends(get_services),
):
    mysql = svc["mysql"]
    log_writer = svc["log_writer"]

    total = mysql.count_by_rating(rating)
    offset = (page - 1) * RESULTS_PER_PAGE
    films = mysql.search_by_rating(rating, RESULTS_PER_PAGE, offset)

    log_writer.log_search("rating", {"rating": rating, "page": page}, len(films))

    return templates.TemplateResponse(
        request, "index.html",
        {
            "request": request, "films": films, "total_found": total, "page": page,
            "search_type": "rating", "rating_val": rating,
            "categories": mysql.get_all_categories(), "min_year": mysql.get_year_range()[0], "max_year": mysql.get_year_range()[1],
            "ratings": mysql.get_all_ratings()
        }
    )

# ---------- API-эндпоинты статистики (возвращают HTML) ----------

@app.get("/stats", response_class=HTMLResponse)
async def view_stats(request: Request, limit: int = 10, svc=Depends(get_services)):
    log_stats = svc["log_stats"]
    
    return templates.TemplateResponse(
        request, "stats.html",
        {
            "request": request,
            "limit": limit,
            "top_keywords": log_stats.get_top_keyword_searches(limit),
            "top_genres": log_stats.get_top_genre_searches(limit),
            "recent": log_stats.get_recent_searches(limit)
        }
    )