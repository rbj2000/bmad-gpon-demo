#!/usr/bin/env python3
# =============================================================================
# run_demo.py
# Purpose: Single-command orchestrator for the GPON demo: generate → load.
# Assumptions: Python 3.10+, dependencies installed per target.
# =============================================================================

"""Run the full GPON synthetic data demo pipeline.

Usage::

    # Generate data and load into NetBox
    python run_demo.py --target netbox

    # Minimal smoke test
    python run_demo.py --target netbox --preset minimal

    # Medium dataset with Slovak cities
    python run_demo.py --target kuwaiba --preset medium --region bratislava

    # Stress test, generate only
    python run_demo.py --preset stress-test --generate-only

    # Load into both targets
    python run_demo.py --target both

    # Dry run (no actual API calls)
    python run_demo.py --target netbox --dry-run
"""

import argparse
import logging
import os
import subprocess
import sys
import time
from pathlib import Path

log = logging.getLogger(__name__)

# Resolve paths relative to this script (repo root)
REPO_ROOT = Path(__file__).resolve().parent
GENERATE_DIR = REPO_ROOT / "generate"
LOAD_DIR = REPO_ROOT / "load"
OUTPUT_DIR = REPO_ROOT / "output"


def run_command(cmd: list[str], description: str) -> bool:
    """Run a subprocess command and return success status."""
    log.info("Running: %s", description)
    log.debug("Command: %s", " ".join(cmd))
    result = subprocess.run(cmd, capture_output=False)
    if result.returncode != 0:
        log.error("%s failed with exit code %d", description, result.returncode)
        return False
    log.info("%s completed successfully", description)
    return True


def resolve_config(preset: str | None, region: str | None) -> Path:
    """Build a resolved config by merging preset and region into base config.

    Returns the path to the (possibly temporary) resolved config file.
    """
    if preset is None and region is None:
        return GENERATE_DIR / "config.yaml"

    # Import resolver from the generate directory
    sys.path.insert(0, str(GENERATE_DIR))
    try:
        import yaml
        from config_resolver import resolve_preset, resolve_region_profile

        with open(GENERATE_DIR / "config.yaml") as f:
            cfg = yaml.safe_load(f)

        if preset is not None:
            cfg = resolve_preset(preset, cfg)
        if region is not None:
            cfg = resolve_region_profile(region, cfg)

        # Write resolved config to a temp file in the output dir
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        resolved_path = OUTPUT_DIR / "_resolved_config.yaml"
        with open(resolved_path, "w") as f:
            yaml.dump(cfg, f, default_flow_style=False, sort_keys=False)
        log.info("Resolved config written to %s", resolved_path)
        return resolved_path
    finally:
        sys.path.pop(0)


def generate_data(config_path: Path, seed: int = 42,
                   include_services: bool = False) -> bool:
    """Run the synthetic data generator."""
    cmd = [
        sys.executable,
        str(GENERATE_DIR / "generate_synthetic_data.py"),
        "--config", str(config_path),
        "--output-dir", str(OUTPUT_DIR),
        "--seed", str(seed),
    ]
    if include_services:
        cmd.append("--include-services")
    return run_command(cmd, "Synthetic data generation")


def load_data(target: str, dry_run: bool = False, workers: int = 1) -> bool:
    """Run the data loader for a specific target."""
    cmd = [
        sys.executable,
        str(LOAD_DIR / "load_data.py"),
        "--adapter", target,
        "--config", str(LOAD_DIR / "load-config.yaml"),
        "--data-dir", str(OUTPUT_DIR),
        "--workers", str(workers),
    ]
    if dry_run:
        cmd.append("--dry-run")
    return run_command(cmd, f"Load data into {target}")


COMPOSE_FILES: dict[str, str] = {
    "netbox": str(REPO_ROOT / "docker" / "docker-compose.netbox.yml"),
    "kuwaiba": str(REPO_ROOT / "docker" / "docker-compose.kuwaiba.yml"),
}


def reset_target(target: str) -> bool:
    """Restart a target's Docker containers with fresh volumes."""
    compose_file = COMPOSE_FILES.get(target)
    if not compose_file or not Path(compose_file).exists():
        log.error("Docker compose file not found for %s: %s", target, compose_file)
        return False

    log.info("Resetting %s: down -v + up -d", target)
    result = subprocess.run(
        ["docker", "compose", "-f", compose_file, "down", "-v"],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        log.error("docker compose down -v failed for %s: %s", target, result.stderr)
        return False

    result = subprocess.run(
        ["docker", "compose", "-f", compose_file, "up", "-d"],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        log.error("docker compose up -d failed for %s: %s", target, result.stderr)
        return False

    return True


def health_check(target: str, retries: int = 60, interval: float = 3.0) -> bool:
    """Wait for target system to become healthy."""
    for attempt in range(1, retries + 1):
        if _probe_target(target):
            return True
        if attempt < retries:
            log.debug("Waiting for %s... (%d/%d)", target, attempt, retries)
            time.sleep(interval)
    return False


def _probe_target(target: str) -> bool:
    """Single health probe for a target."""
    if target == "netbox":
        try:
            import requests
            # NetBox v4.x requires auth even for /api/status/
            token = "0123456789abcdef0123456789abcdef01234567"
            resp = requests.get(
                "http://localhost:8000/api/status/",
                headers={"Authorization": f"Token {token}"},
                timeout=5,
            )
            return resp.status_code == 200
        except Exception:
            return False
    elif target == "kuwaiba":
        try:
            import requests
            # SOAP WS runs on port 8081 (ws.port in application.properties)
            resp = requests.get("http://localhost:8881/kuwaiba/KuwaibaService?wsdl", timeout=5)
            return resp.status_code == 200
        except Exception:
            return False
    return False


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run the full GPON synthetic data demo pipeline."
    )
    parser.add_argument(
        "--target", choices=["netbox", "kuwaiba", "both"],
        help="Target system(s) to load data into.",
    )
    parser.add_argument(
        "--preset", choices=["minimal", "small", "medium", "large", "stress-test"],
        default=None,
        help="Size/depth/complexity preset (default: use config.yaml as-is).",
    )
    parser.add_argument(
        "--region", default=None,
        help="Region name (czech, bratislava, vienna) or path to region YAML.",
    )
    parser.add_argument(
        "--generate-only", action="store_true",
        help="Only generate synthetic data, don't load.",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Generate data but only simulate loading.",
    )
    parser.add_argument(
        "--seed", type=int, default=42,
        help="Random seed for data generation (default: 42).",
    )
    parser.add_argument(
        "--workers", type=int, default=4,
        help="Number of parallel threads per entity type for loading (default: 4).",
    )
    parser.add_argument(
        "--include-services", action="store_true",
        help="Generate and load CFS/RFS service inventory.",
    )
    args = parser.parse_args()

    if not args.generate_only and not args.target:
        parser.error("--target is required unless --generate-only is set")

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    targets = (
        ["netbox", "kuwaiba"] if args.target == "both"
        else [args.target] if args.target
        else []
    )
    timings: dict[str, float] = {}
    overall_start = time.time()

    # Step 0: Resolve config from preset + region
    config_path = resolve_config(args.preset, args.region)
    if args.preset:
        print(f"Using preset: {args.preset}")
    if args.region:
        print(f"Using region: {args.region}")

    # Step 1: Reset targets (fresh volumes) and wait for healthy (unless generate-only or dry-run)
    if not args.generate_only and not args.dry_run:
        for target in targets:
            print(f"\nResetting {target} (clean volumes)...")
            if not reset_target(target):
                log.error("Failed to reset %s", target)
                sys.exit(1)
            print(f"  Waiting for {target} to become healthy...")
            if not health_check(target):
                log.error(
                    "%s did not become healthy after reset.",
                    target,
                )
                sys.exit(1)
            print(f"  {target} is healthy.")

    # Step 2: Generate synthetic data
    print("\n--- Generating synthetic data ---")
    t0 = time.time()
    if not generate_data(config_path, seed=args.seed,
                         include_services=args.include_services):
        sys.exit(1)
    timings["generate"] = time.time() - t0

    if args.generate_only:
        print(f"\nData generated in {timings['generate']:.1f}s")
        print(f"Output: {OUTPUT_DIR}/")
        return

    # Step 3: Load into target(s)
    for target in targets:
        print(f"\n--- Loading into {target} ---")
        t0 = time.time()
        if not load_data(target, dry_run=args.dry_run, workers=args.workers):
            log.error("Loading into %s failed", target)
            if len(targets) == 1:
                sys.exit(1)
        timings[f"load_{target}"] = time.time() - t0

    # Summary
    total = time.time() - overall_start
    print("\n" + "=" * 50)
    print("DEMO PIPELINE SUMMARY")
    print("=" * 50)
    for step, elapsed in timings.items():
        print(f"  {step:<20} {elapsed:>8.1f}s")
    print(f"  {'TOTAL':<20} {total:>8.1f}s")
    print("=" * 50)

    if args.include_services:
        print("\nService inventory: CFS/RFS enabled")
        svc_dir = OUTPUT_DIR
        for svc_file in ["subscribers.csv", "services_cfs.csv", "services_rfs.csv", "service_resource_links.csv"]:
            fpath = svc_dir / svc_file
            if fpath.exists():
                import csv as _csv
                with open(fpath) as _f:
                    count = sum(1 for _ in _csv.reader(_f)) - 1  # minus header
                print(f"  {svc_file}: {count} rows")

    if args.dry_run:
        print("\n(Dry run — no data was actually loaded)")
    else:
        for target in targets:
            if target == "netbox":
                print(f"\nVerify NetBox: http://localhost:8000")
                if args.include_services:
                    print("  Custom Objects: Plugins → Custom Objects → GPONSubscriber / CFS / RFS")
            elif target == "kuwaiba":
                print(f"\nVerify Kuwaiba: http://localhost:8880")
                if args.include_services:
                    print("  Service Manager: customer pool → customers → CFS/RFS")


if __name__ == "__main__":
    main()
