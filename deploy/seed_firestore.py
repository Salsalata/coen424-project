"""Load catalog-service/data/products.json into Firestore, keeping the ids
(p001...). Run once from your laptop after `gcloud auth application-default login`:

    pip install google-cloud-firestore
    source deploy/config.sh && python deploy/seed_firestore.py
"""

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "catalog-service"))

from app.products.firestore_repository import FirestoreProductRepository  # noqa: E402
from app.seed import seed_products  # noqa: E402

project = os.environ.get("PROJECT_ID")
if not project or project.startswith("REPLACE"):
    sys.exit("Set PROJECT_ID first (source deploy/config.sh)")
repo = FirestoreProductRepository(project)
seed_products(repo, ROOT / "catalog-service" / "data" / "products.json")
print(f"Seeded {len(repo.list())} products into Firestore project {project}")
