"""Igual que en el notebook: toma la distribución 'starter', registra llama3.1:8b de Ollama y levanta Llama Stack."""
import os
import yaml
import llama_stack

modelo = os.getenv("MODELO_OLLAMA", "llama3.1:8b")
config_path = os.path.join(os.path.dirname(llama_stack.__file__), "distributions", "starter", "config.yaml")
with open(config_path) as f:
    config = yaml.safe_load(f)

config["registered_resources"]["models"].append({
    "model_id": modelo, "provider_id": "ollama", "provider_model_id": modelo, "model_type": "llm",
})
destino = "/data/config_llama_stack.yaml"
with open(destino, "w") as f:
    yaml.dump(config, f, default_flow_style=False, sort_keys=False)

os.execvp("llama", ["llama", "stack", "run", destino, "--port", "8321"])
