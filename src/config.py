import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Base directories
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "raw"
OUTPUT_DIR = PROJECT_ROOT / "outputs"

# Ensure output directory exists
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# API Configuration
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")

# Expected Data File Paths
TICKETS_CSV = DATA_DIR / "tickets.csv"
CUSTOMERS_CSV = DATA_DIR / "customers.csv"
ORDERS_CSV = DATA_DIR / "orders.csv"
PRODUCTS_CSV = DATA_DIR / "products.csv"

# Handle agent.csv vs agents.csv gracefully
if (DATA_DIR / "agents.csv").exists():
    AGENTS_CSV = DATA_DIR / "agents.csv"
else:
    AGENTS_CSV = DATA_DIR / "agent.csv"

README_TXT = DATA_DIR / "README.txt"
SUPPORT_POLICY_PDF = DATA_DIR / "support-policy.pdf"
EMAIL_THREAD_TXT = DATA_DIR / "email-thread.txt"
