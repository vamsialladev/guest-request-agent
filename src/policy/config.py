"""Settings for the copied Project 1 retrieval modules (retrieve.py, ingest.py import these names).

Project 2 always runs keyword-only (BM25): light enough for Streamlit Community Cloud, no PyTorch. The documents are
Project 1's synthetic hotel documents, copied by scripts/sync_policy.py; the index is built on first use.
"""

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
RAW_DIR = ROOT / "data" / "policy" / "raw"
INDEX_DIR = Path(os.getenv("POLICY_INDEX_DIR", ROOT / "data" / "policy_index"))
EMBED_MODEL = "sentence-transformers/all-MiniLM-L6-v2"  # unused: embeddings are off in Project 2
USE_EMBEDDINGS = False
TOP_K = int(os.getenv("POLICY_TOP_K", "3"))
SHARED = "shared"
