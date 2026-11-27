import os
from pathlib import Path

# Для RTX 4060 можно задать RAG_MODEL=huihui_ai/qwen2.5-abliterate:7b.
# Для 1660 super можно задать RAG_MODEL", "huihui_ai/qwen2.5-abliterate:3b
TARGET_MODEL = os.getenv("RAG_MODEL", "huihui_ai/qwen2.5-abliterate:3b")
# GUARD_BASE = "llama-guard3:8b-q4_K_M"
# GUARD_MODEL = "rag-guard:8b"
GUARD_BASE = "llama-guard3:1b-q4_K_M"
GUARD_MODEL = "rag-guard:1b"  # Локальное имя тех же весов с шаблоном для User/Agent.
EMBEDDING_DEVICE = os.getenv("EMBEDDING_DEVICE", "cpu")
os.environ.setdefault("ANONYMIZED_TELEMETRY", "False")  # Локальный индекс Chroma.
NUM_CTX = 4096

SYSTEM_PROMPT = (
    "Ты помогаешь команде учебного проекта разбираться в её документах. "
    "Используй приведённые выдержки как источник фактов. "
    "Отвечай кратко и по-русски. Если данных мало, скажи об этом."
)

ROOT = Path(__file__).resolve().parent
KNOWLEDGE_DIR = ROOT / "knowledge"
DB_DIR = ROOT / "chroma_db"
AUDIT_FILE = ROOT / "runs" / "guard_events.jsonl"


def read_flag(value):
    value = str(value).strip().lower()
    if value in ("1", "true", "on", "yes"):
        return True
    if value in ("0", "false", "off", "no"):
        return False
    raise ValueError("Для guardrails_enabled укажите true/false или 1/0.")


GUARDRAILS_ENABLED = read_flag(os.getenv("GUARDRAILS_ENABLED", "1"))