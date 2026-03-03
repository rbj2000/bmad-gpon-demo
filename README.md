# BMAD GPON Demo

One-command demo of a GPON access network inventory loaded into **NetBox** (REST) or **Kuwaiba** (SOAP) — synthetic sites, OLTs with chassis internals, splitters, ONTs, fiber connections, and optional CFS/RFS service inventory.

## Architecture

```
┌─────────────┐     CSV      ┌──────────────┐     REST/SOAP     ┌─────────────────┐
│  generate/  │ ──────────►  │    load/     │ ───────────────►  │ NetBox / Kuwaiba│
│  Synthetic  │   sites,     │  Adapter     │   create objects  │ (Docker)        │
│  Data Gen   │   OLTs,      │  Pattern     │   via native API  │                 │
│             │   ONTs...    │              │                   │                 │
└─────────────┘              └──────────────┘                   └─────────────────┘
       ▲                                                                ▲
       │                                                                │
  profiles/                                                      docker/
  preset + region                                            compose files
  YAML configs                                               + custom image
```

## Quick Start

```bash
git clone https://github.com/<your-user>/bmad-gpon-demo.git
cd bmad-gpon-demo
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Minimal smoke test (~30 records, ~2 min including container startup)
python run_demo.py --preset minimal --target netbox
```

## Usage Examples

```bash
# Standard demo (~615 records, 5 Czech cities)
python run_demo.py --preset small --target kuwaiba

# Both targets side by side
python run_demo.py --preset small --target both

# Regional variant (Bratislava districts)
python run_demo.py --preset medium --region bratislava --target kuwaiba

# With CFS/RFS service inventory (NetBox — Custom Objects plugin)
python run_demo.py --preset small --target netbox --include-services

# With CFS/RFS service inventory (Kuwaiba — native Service Manager)
python run_demo.py --preset small --target kuwaiba --include-services

# Generate data only (no Docker needed)
python run_demo.py --preset small --generate-only

# Dry run (generate + simulate loading, no API calls)
python run_demo.py --preset small --target netbox --dry-run
```

## Presets

| Preset | Sites | OLTs | ONTs | Total Records | Use Case |
|--------|-------|------|------|---------------|----------|
| `minimal` | 1 | 1 | 8 | ~30 | Smoke test |
| `small` | 5 | 5 | 120 | ~615 | Standard demo |
| `medium` | 10 | 15 | 500 | ~2,500 | Extended demo |
| `large` | 25 | 50 | 3,000 | ~6,000 | Load testing |
| `stress-test` | 50 | 100 | 12,000 | ~25,000 | Stress testing |

## Regions

| Region | Description |
|--------|-------------|
| `czech` (default) | 5 Czech cities (Prague, Brno, Ostrava, Plzen, Liberec) |
| `bratislava` | Bratislava districts |
| `vienna` | Vienna districts |
| Custom YAML | Pass a file path to `--region` |

## Target Systems

| | NetBox | Kuwaiba |
|---|--------|---------|
| **API** | REST / JSON | SOAP / XML |
| **Web UI** | http://localhost:8000 | http://localhost:8880 |
| **Credentials** | `admin` / `admin` | `admin` / `kuwaiba` |
| **Services** | Custom Objects plugin | Native Service Manager |
| **Visualization** | Topology Views plugin | OSP Module |

## What Gets Loaded

**Physical inventory:**
- Sites (central offices)
- Racks (per site)
- OLTs with chassis internals (slots, line cards, SFP transceivers, ports)
- Fiber splitters (1:8, 1:16, 1:32)
- ONTs (customer premises equipment)
- Fiber connections (OLT port → splitter → ONT)

**Service inventory** (with `--include-services`):
- Subscribers (customer records)
- CFS — Customer-Facing Services (broadband plans)
- RFS — Resource-Facing Services (resource allocations)
- Service-to-resource links

## Project Structure

```
bmad-gpon-demo/
├── run_demo.py              # Main entry point
├── generate/                # Synthetic data generation
│   ├── generate_synthetic_data.py
│   ├── config_resolver.py
│   ├── value_pools.py
│   └── config.yaml
├── profiles/                # Preset & region profiles
│   ├── preset-minimal.yaml
│   ├── preset-small.yaml
│   └── ...
├── load/                    # Target loaders (adapter pattern)
│   ├── load_data.py
│   ├── base_adapter.py
│   ├── netbox_adapter.py
│   ├── kuwaiba_adapter.py
│   └── load-config.yaml
├── docker/                  # Docker compose files
│   ├── docker-compose.kuwaiba.yml
│   ├── docker-compose.netbox.yml
│   └── netbox-custom/
├── walkthroughs/            # Interactive UI tours (Playwright)
├── docs/                    # Demo guides & evolution story
└── screenshots/             # Visualization screenshots
```

## Prerequisites

- Python 3.10+
- Docker (with `docker compose`)
- ~2 GB free disk space for container images

## Interactive Walkthroughs

After loading data, run an interactive UI walkthrough using Playwright:

```bash
pip install playwright && playwright install chromium

# NetBox walkthrough
python walkthroughs/netbox/walkthrough.py

# Kuwaiba walkthrough
python walkthroughs/kuwaiba/walkthrough.py
```

## Documentation

- [Demo Guide](docs/gpon-demo-guide.md) — presenter playbook with UI walkthrough
- [Setup Instructions](docs/demo-instructions.md) — detailed setup guide
- [Demo Evolution](docs/DEMO_EVOLUTION.md) — how this demo was built iteratively (9 phases)

## License

MIT
