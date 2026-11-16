import os
import secrets
from pathlib import Path

# MySQL stores structured application data.
TORTOISE_ORM = {
    "connections": {
        "default": {
            "engine": "tortoise.backends.mysql",
            "credentials": {
                "host": "localhost",
                "port": 3306,
                # Name of the database populated by ai_rag.sql.
                "database": "ai_rag",
                "user": "root",
                # Password for the MySQL account.
                "password": "123456",
                "minsize": 1,
                "maxsize": 10,
                "charset": "utf8mb4",
                "echo": True
            }
        },
    },
    "apps": {
      "models": {
          # Tortoise discovers all model classes exported by this package.
          "models": ["models"],
          "default_connection": "default",
      }
    },
    # The database uses naive datetimes in the configured timezone.
    "use_tz": False,
    "timezone": "UTC"
}

# PostgreSQL stores embeddings and retrieval metadata keyed by the MySQL knowledge_chunk ID.
PGVECTOR = {
    "host": "localhost",
    "port": 5432,
    "database": "ai_rag_vector",
    "user": "postgres",
    "password": "123456",
    # Match the enabled embedding model and the pgvector column dimension.
    "dimension": 1024,
}

def _jwt_secret():
    configured = os.environ.get("JWT_SECRET")
    if configured:
        if len(configured) < 32:
            raise RuntimeError("JWT_SECRET must contain at least 32 characters")
        return configured
    path = Path(os.environ.get("JWT_SECRET_FILE", str(Path(__file__).parent / ".local-jwt-secret")))
    path.parent.mkdir(parents=True, exist_ok=True)
    # Publish a fully written file atomically; concurrent workers never read an empty key.
    import tempfile
    with tempfile.NamedTemporaryFile(mode="w", dir=path.parent, delete=False) as handle:
        temporary = Path(handle.name)
        handle.write(secrets.token_urlsafe(48))
        handle.flush()
        os.fsync(handle.fileno())
    try:
        try:
            os.link(temporary, path)
        except FileExistsError:
            pass
        value = path.read_text().strip()
        if len(value) < 32:
            raise RuntimeError("Local signing key is invalid; set JWT_SECRET or regenerate the local key")
        return value
    finally:
        temporary.unlink()

JWT_SECRET = _jwt_secret()
JWT_ALGORITHM = "HS256"
JWT_EXPIRE_HOURS = 24


for _key, _env in (("host","MYSQL_HOST"), ("port","MYSQL_PORT"), ("database","MYSQL_DATABASE"), ("user","MYSQL_USER"), ("password","MYSQL_PASSWORD")):
    if _env in os.environ:
        TORTOISE_ORM["connections"]["default"]["credentials"][_key] = int(os.environ[_env]) if _key == "port" else os.environ[_env]
for _key, _env in (("host","PGHOST"), ("port","PGPORT"), ("database","PGDATABASE"), ("user","PGUSER"), ("password","PGPASSWORD")):
    if _env in os.environ:
        PGVECTOR[_key] = int(os.environ[_env]) if _key == "port" else os.environ[_env]

PUBLIC_API_BASE = os.environ.get("PUBLIC_API_BASE", "http://127.0.0.1:9090").rstrip("/")
UPLOAD_DIR = os.environ.get("UPLOAD_DIR", "files")
OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL")
