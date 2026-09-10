from __future__ import annotations

import argparse
from pathlib import Path

import uvicorn

from credit_risk_pd.api import create_scoring_app
from credit_risk_pd.serving import load_scoring_service_from_manifest


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Serve a verified credit-risk PD model through a local reference API."
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=Path("models/deployment_manifest.json"),
        help="Deployment manifest; its sibling model artifact is loaded and verified.",
    )
    parser.add_argument("--host", default="127.0.0.1", help="Local bind address.")
    parser.add_argument("--port", type=int, default=8000, help="Local bind port.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    service = load_scoring_service_from_manifest(args.manifest)
    uvicorn.run(create_scoring_app(service), host=args.host, port=args.port)


if __name__ == "__main__":
    main()
