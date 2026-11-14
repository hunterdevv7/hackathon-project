"""Central settings, read once from environment / .env."""
import os

from dotenv import load_dotenv

load_dotenv()

QUANTUM_MODE = os.getenv("QUANTUM_MODE", "mock").strip().lower()
BATCH_SIZE = int(os.getenv("BATCH_SIZE", "64"))
MAX_BATCH = 1024
PORT = int(os.getenv("PORT", "5000"))

# Quantum Rings credentials (only needed when QUANTUM_MODE=quantumrings).
# QR_TOKEN is the license token; QR_ACCOUNT is the email you registered with.
QR_TOKEN = os.getenv("QR_TOKEN", "").strip()
QR_ACCOUNT = os.getenv("QR_ACCOUNT", "").strip()
QR_BACKEND = os.getenv("QR_BACKEND", "scarlet_quantum_rings").strip()
