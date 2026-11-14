"""Central settings, read once from environment / .env."""
import os

from dotenv import load_dotenv

load_dotenv()

QUANTUM_MODE = os.getenv("QUANTUM_MODE", "mock").strip().lower()
BATCH_SIZE = int(os.getenv("BATCH_SIZE", "64"))
MAX_BATCH = 1024
PORT = int(os.getenv("PORT", "5000"))
