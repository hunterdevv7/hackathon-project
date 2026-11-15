"""Central settings, read once from environment / .env."""
import os

from dotenv import load_dotenv

load_dotenv()

QUANTUM_MODE = os.getenv("QUANTUM_MODE", "mock").strip().lower()
BATCH_SIZE = int(os.getenv("BATCH_SIZE", "64"))
MAX_BATCH = 1024
PORT = int(os.getenv("PORT", "5000"))

# Browser origins allowed to call the API from another site (CORS). Empty = none,
# which is right in production: the page is served by this API, so it's same-origin.
# Frontend work from a separate dev server or a file:// page needs CORS_ORIGINS=*.
CORS_ORIGINS = [o.strip() for o in os.getenv("CORS_ORIGINS", "").split(",") if o.strip()]

# Largest request body accepted. The biggest legitimate body (1024 bits as JSON)
# is about 5 KB; anything bigger is refused with HTTP 413 before it is parsed.
MAX_BODY_BYTES = 64 * 1024

# Quantum Rings credentials (only needed when QUANTUM_MODE=quantumrings).
# QR_TOKEN is the license token; QR_ACCOUNT is the email you registered with.
QR_TOKEN = os.getenv("QR_TOKEN", "").strip()
QR_ACCOUNT = os.getenv("QR_ACCOUNT", "").strip()
QR_BACKEND = os.getenv("QR_BACKEND", "scarlet_quantum_rings").strip()
