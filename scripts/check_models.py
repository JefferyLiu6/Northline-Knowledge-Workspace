"""Check that local Ollama model digests match the recorded demo/evaluation models."""
import argparse,json,urllib.request
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument("--url",default="http://127.0.0.1:11434");args=p.parse_args()
expected=json.loads((Path(__file__).resolve().parents[1]/"evaluations/results/environment.json").read_text())["ollama_models"]
with urllib.request.urlopen(args.url.rstrip("/")+"/api/tags",timeout=10) as response:
    actual={m["name"]:m["digest"] for m in json.load(response)["models"]}
errors=[]
for model in expected:
    if actual.get(model["name"])!=model["digest"]:
        errors.append(model["name"])
if errors:
    raise SystemExit("Model missing or digest differs: "+", ".join(errors)+". Pull the documented models; if intentionally changing embeddings, rebuild the index and rerun evaluation.")
print("PASS: local model digests match the recorded demo models.")
