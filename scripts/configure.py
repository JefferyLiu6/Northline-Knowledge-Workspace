"""Generate local Compose configuration without overwriting an existing .env."""
import argparse, os, secrets
from pathlib import Path
parser=argparse.ArgumentParser()
parser.add_argument("--port",type=int,default=8080)
args=parser.parse_args()
if not 1024 <= args.port <= 65535:
    parser.error("Choose a port between 1024 and 65535")
path=Path(__file__).resolve().parents[1]/".env"
try:
    fd=os.open(path,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
except FileExistsError:
    print(".env already exists; preserved without changes.")
else:
    with os.fdopen(fd,"w") as handle:
        handle.write(f"APP_PORT={args.port}\n")
        for name in ("MYSQL_ROOT_PASSWORD","MYSQL_PASSWORD","PGPASSWORD"):
            handle.write(f"{name}={secrets.token_urlsafe(32)}\n")
        handle.write("OLLAMA_BASE_URL=http://host.docker.internal:11434/v1\n")
    print("Created private .env. Next: docker compose up --build -d --wait")
