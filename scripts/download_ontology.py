#!/usr/bin/env python3
"""Download and manage ontologies for KnowledgeGraphBuilder.

This script handles downloading the AI Planning Ontology from GitHub
and organizing it with version management in data/ontology/.

Usage:
    python scripts/download_ontology.py [ontology] [options]

Examples:
    python scripts/download_ontology.py
    python scripts/download_ontology.py planning -v 1.0
    python scripts/download_ontology.py planning --force
    python scripts/download_ontology.py --list-downloaded
    python scripts/download_ontology.py planning --cleanup
"""

import argparse
from pathlib import Path
from typing import Optional
from urllib.request import urlopen


# Configuration
GITHUB_ORG = "BharathMuppasani"
GITHUB_REPO = "AI-Planning-Ontology"
GITHUB_BRANCH = "main"

ONTOLOGIES = {
    "planning": {
        "github_path": "models/plan-ontology.owl",
        "local_name": "plan-ontology",
        "versions": ["1.0"],
        "default": "1.0",
    }
}

DATA_DIR = Path(__file__).parent.parent / "data" / "ontology"


def get_github_url(ontology_key: str, version: str | None = None) -> str:
    """Generate GitHub raw content URL for ontology file.

    Args:
        ontology_key: Ontology identifier ('planning')
        version: Ontology version ('1.0', '2.0', etc.)

    Returns:
        Full GitHub raw content URL
    """
    if version is None:
        version = ONTOLOGIES[ontology_key]["default"]

    github_path = ONTOLOGIES[ontology_key]["github_path"]
    url = (
        f"https://raw.githubusercontent.com/{GITHUB_ORG}/{GITHUB_REPO}/"
        f"{GITHUB_BRANCH}/{github_path}"
    )
    return url


def download_ontology(
    ontology_key: str,
    version: str | None = None,
    force: bool = False,
) -> Path:
    """Download ontology from GitHub.

    Args:
        ontology_key: Ontology identifier ('planning')
        version: Ontology version (defaults to latest)
        force: Force re-download even if file exists

    Returns:
        Path to downloaded file

    Raises:
        ValueError: If ontology_key or version invalid
        IOError: If download fails
    """
    if ontology_key not in ONTOLOGIES:
        raise ValueError(
            f"Unknown ontology: {ontology_key}. "
            f"Available: {list(ONTOLOGIES.keys())}"
        )

    if version is None:
        version = ONTOLOGIES[ontology_key]["default"]

    if version not in ONTOLOGIES[ontology_key]["versions"]:
        raise ValueError(
            f"Unknown version {version} for {ontology_key}. "
            f"Available: {ONTOLOGIES[ontology_key]['versions']}"
        )

    # Construct local filename
    local_name = ONTOLOGIES[ontology_key]["local_name"]
    filename = f"{local_name}-v{version}.owl"
    filepath = DATA_DIR / filename

    # Skip if already exists (unless force)
    if filepath.exists() and not force:
        print(f"✓ {filename} already exists (use --force to re-download)")
        return filepath

    # Download from GitHub
    url = get_github_url(ontology_key, version)
    print(f"⏳ Downloading from {url}...")

    try:
        with urlopen(url) as response:
            content = response.read()
            filepath.parent.mkdir(parents=True, exist_ok=True)
            filepath.write_bytes(content)
            print(f"✅ Downloaded {filename} ({len(content) / 1024:.1f} KB)")
            return filepath
    except Exception as e:
        raise IOError(f"Failed to download {ontology_key}: {e}") from e


def list_ontologies() -> None:
    """List all available ontologies and versions."""
    print("\n📚 Available Ontologies\n" + "=" * 40)

    for ontology_key, config in ONTOLOGIES.items():
        print(f"\n{ontology_key.upper()}")
        print(f"  Versions: {', '.join(config['versions'])}")
        print(f"  Default: {config['default']}")
        print(f"  Local name: {config['local_name']}")


def list_downloaded() -> None:
    """List locally downloaded ontologies."""
    if not DATA_DIR.exists():
        print("No ontologies downloaded yet")
        return

    files = sorted(DATA_DIR.glob("*.owl"))
    if not files:
        print("No ontologies found in data/ontology/")
        return

    print("\n📦 Downloaded Ontologies\n" + "=" * 40)
    for filepath in files:
        size_kb = filepath.stat().st_size / 1024
        print(f"  {filepath.name:.<40} {size_kb:>6.1f} KB")


def cleanup_old_versions(ontology_key: str, keep_latest: int = 2) -> None:
    """Clean up old versions, keeping latest N versions.

    Args:
        ontology_key: Ontology identifier
        keep_latest: Number of latest versions to keep
    """
    if ontology_key not in ONTOLOGIES:
        raise ValueError(f"Unknown ontology: {ontology_key}")

    local_name = ONTOLOGIES[ontology_key]["local_name"]
    pattern = f"{local_name}-v*.owl"
    files = sorted(DATA_DIR.glob(pattern), reverse=True)

    if len(files) <= keep_latest:
        print(f"✓ Already have {len(files)} versions (keeping {keep_latest})")
        return

    for filepath in files[keep_latest:]:
        print(f"🗑️  Removing {filepath.name}")
        filepath.unlink()


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Download and manage ontologies for KnowledgeGraphBuilder"
    )
    parser.add_argument(
        "ontology",
        nargs="?",
        default="planning",
        help="Ontology to download (planning)",
    )
    parser.add_argument(
        "-v",
        "--version",
        help="Ontology version (defaults to latest)",
    )
    parser.add_argument(
        "-f",
        "--force",
        action="store_true",
        help="Force re-download",
    )
    parser.add_argument(
        "-l",
        "--list",
        action="store_true",
        help="List available ontologies",
    )
    parser.add_argument(
        "-d",
        "--list-downloaded",
        action="store_true",
        help="List downloaded ontologies",
    )
    parser.add_argument(
        "--cleanup",
        action="store_true",
        help="Clean up old versions (keep latest 2)",
    )

    args = parser.parse_args()

    # Handle listing
    if args.list:
        list_ontologies()
        return 0

    if args.list_downloaded:
        list_downloaded()
        return 0

    # Handle cleanup
    if args.cleanup:
        cleanup_old_versions(args.ontology)
        return 0

    # Download ontology
    try:
        filepath = download_ontology(
            args.ontology,
            version=args.version,
            force=args.force,
        )
        print(f"\n💾 Saved to: {filepath}")
    except (ValueError, IOError) as e:
        print(f"❌ Error: {e}")
        return 1

    return 0


if __name__ == "__main__":
    exit(main())
