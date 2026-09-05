# 🚀 Rocket Trajectory API

Навчальний pet-проєкт, AI-Engineering портфоліо-піс, що еволюціонував з простого фізичного симулятора в повноцінний backend-стек з RAG, structured output та AI-агентом з tool-use.

<!-- TODO: сюди скріншот або GIF з /static/index.html — canvas-анімація ракети + чат. Найкраща частина проєкту зараз не має жодного візуалу в README. -->

## Стек

- **Backend:** FastAPI (async), SQLAlchemy 2.0 (async), SQLite
- **AI/ML:** Claude API (Anthropic SDK, streaming + tool use), sentence-transformers, ChromaDB, Instructor (Pydantic v2 structured output)
- **Frontend:** Vanilla JS + HTML5 Canvas (без фреймворків), кастомна 2D-анімація

## Структура

```
app/
├── main.py                 # FastAPI app, усі ендпоінти
├── models.py                # SQLAlchemy модель Simulation
├── schemas.py                # Pydantic схеми (request/response)
├── database.py                # async engine, сесії
├── config.py                   # pydantic-settings, читає .env
├── simulation_service.py        # обгортка над фізикою (physics/)
├── rag_service.py                 # embeddings + ChromaDB + /ask (RAG)
└── agent.py                        # tool-use агент з Claude API: пам'ять діалогу + NDJSON-стрімінг

physics/
├── rocket.py                # клас Rocket
└── environment.py            # клас SimulationEnvironment, Euler-інтеграція з опором повітря

static/
├── index.html                # UI: canvas-візуалізатор + телеметрія + чат
├── style.css
└── script.js                  # анімація, drag, порівняння симуляцій, чат (streaming + tool-trace)

tests/
├── test_physics.py           # фізика: апогей без опору, опір, двигун, парашут, Euler vs RK4
├── test_optimization.py       # golden-section пошук кута, Monte Carlo розкид
└── test_api.py                 # /simulate, /simulations, delete, optimal-angle, dispersion
```

## Що робить проєкт

**Фізична симуляція** — траєкторія ракети з опором повітря, на вибір Euler (semi-implicit) або RK4 інтегрування. Плюс опційно:
- **Двигун** — тяга (Н), час горіння, маса палива: рівномірне вигоряння маси під час горіння, прискорення від тяги додається до гравітації й опору (не політ по готовій `v0`, а розгін з нуля/старту).
- **Парашут** — інший `Cd`/площа, що вмикається автоматично в момент початку падіння (vy < 0).

**Математика над симуляціями:**
- **Пошук оптимального кута** — без опору повітря оптимум завжди 45°, з квадратичним опором пік дальності зсувається нижче і немає формули — шукається чисельно golden-section search'ем.
- **Monte Carlo розкид приземлення** — той самий запуск N разів з шумом на кут/швидкість → розкид точок приземлення (μ, σ), а не одна траєкторія.

**REST API:**
- `POST /simulate` — запустити нову симуляцію (з опційним двигуном/парашутом/RK4)
- `GET /simulations`, `GET /simulations/{id}` — список і деталі
- `DELETE /simulations/{id}` — видалення (з SQL і ChromaDB)
- `POST /simulate/optimal-angle` — знайти кут з максимальною дальністю
- `POST /simulate/dispersion` — Monte Carlo розкид приземлення (аналіз, не зберігається в БД)
- `POST /ask` — RAG: питання природною мовою → semantic search по ChromaDB → Claude дає structured-відповідь (Instructor)
- `POST /agent/chat` — AI-агент з tool use, відповідь одним блоком (для curl/скриптів)
- `POST /agent/chat/stream` — той самий агент, але NDJSON-стрім: токени відповіді в реальному часі + окрема подія на кожен виклик інструменту (`compare_simulations`, `run_new_simulation`, `find_optimal_angle` тощо), плюс пам'ять діалогу за `session_id`

Повна інтерактивна документація — на `/docs` (Swagger).

**Frontend-візуалізатор** (`/static/index.html`):
- Canvas-анімація польоту ракети з інтерполяцією між точками траєкторії
- Drag мишкою по траєкторії, ручне введення часу
- Форма створення нової симуляції прямо в UI (без Swagger) — з опційними секціями двигуна, парашута, вибору методу інтегрування, кнопкою пошуку оптимального кута й Monte Carlo розкидом
- Режим порівняння кількох симуляцій одночасно (кольорові накладені графіки + жива телеметрія кожної) — керується і руками, і агентом ("порівняй симуляції 2, 3 та 4")
- Чат з перемиканням "Питання" (стейтлес RAG) / "Агент" (tool-use, пам'ятає контекст діалогу, показує живий трейс своїх дій, вміє знайти оптимальний кут)

## Запуск локально

Потрібен [uv](https://docs.astral.sh/uv/).

```bash
uv sync
cp .env.example .env   # і вписати свій ANTHROPIC_API_KEY
uv run uvicorn app.main:app --reload
```

Відкрити http://127.0.0.1:8000/static/index.html (візуалізатор) або http://127.0.0.1:8000/docs (Swagger).

## Запуск у Docker

```bash
docker compose up --build
```

Очікує `.env` з `ANTHROPIC_API_KEY` у корені проєкту. `rocket.db` і `chroma_data/` монтуються як volume, щоб дані переживали перезапуск контейнера.

## Тести

```bash
uv run pytest
```

Тести фізики перевіряють апогей без опору повітря (проти аналітичної формули), вплив опору/двигуна/парашута на дальність-апогей-час польоту, узгодженість Euler та RK4. Тести оптимізації перевіряють, що знайдений кут дає дальність не гіршу за 45° і що розкид Monte Carlo росте з шумом. API-тести піднімають окрему тестову SQLite-базу (не чіпають `rocket.db` чи реальний ChromaDB-індекс).

## Відомі обмеження (чесно)

- `confidence` у `/ask` — це самооцінка LLM (high/medium/low), а не метрика, прив'язана до реальної відстані ембеддінгів у ChromaDB. Класична вразливість RAG-систем: LLM не завжди адекватно оцінює власну впевненість. Правильний фікс — прив'язати впевненість до retrieval-score, але пороги потребують емпіричного тюнінгу на реальних даних, тож зараз залишено як є.
- Пам'ять діалогу агента — в оперативній пам'яті процесу (`session_id` → історія повідомлень), без персистентності. Достатньо для демо, не переживе перезапуск сервера чи горизонтальне масштабування на кілька інстансів.
- Двигун — спрощена модель (постійна тяга + лінійне вигоряння маси за `burn_time`), не повне рівняння Ціолковського з питомим імпульсом. Парашут спрацьовує миттєво в момент vy < 0, без затримки розкриття. Monte Carlo розкид — лише вздовж дальності (модель 2D, без бокового вітру/z-осі).
- Це навчальний проєкт без автентифікації — усі ендпоінти публічні.

## Навіщо

Портфоліо-проєкт для позицій AI Engineer — демонструє: async FastAPI, RAG pipeline, structured LLM output, streaming tool-calling агентів з пам'яттю діалогу, і трохи frontend/canvas роботи понад "стандартний" backend-скоуп.
