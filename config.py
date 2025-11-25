"""
Balthazar - Configuration centralisée
Moteur de recherche IA pour corpus documentaire avec format .balthazar
"""
import os

# === INFORMATIONS BALTHAZAR ===
BALTHAZAR_VERSION = "2.0.0"
BALTHAZAR_NAME = "Balthazar"
BALTHAZAR_DESCRIPTION = "Moteur de recherche IA pour corpus documentaire"

# === GESTION DES PROJETS ===
BALTHAZAR_PROJECTS_DIR = "./balthazar_workspace"
BALTHAZAR_CURRENT_PROJECT_FILE = "./balthazar_current.txt"

# === MODÈLES IA BALTHAZAR ===
BALTHAZAR_EMBED_MODEL = "BAAI/bge-small-en-v1.5"
BALTHAZAR_LLM_MODEL = "llama3.2:3b"
BALTHAZAR_OLLAMA_BASE_URL = "http://localhost:11434"
BALTHAZAR_OLLAMA_TIMEOUT = 120.0

# === INDEXATION BALTHAZAR ===
BALTHAZAR_BATCH_SIZE = 500
BALTHAZAR_COLLECTION_NAME = "balthazar_documents"
BALTHAZAR_EMBED_DIM = 384

# === MONITORING BALTHAZAR ===
BALTHAZAR_PROMETHEUS_PORT = 8000

# === EMAIL BALTHAZAR ===
BALTHAZAR_SMTP_HOST = "localhost"
BALTHAZAR_SMTP_FROM = "alert@balthazar.local"