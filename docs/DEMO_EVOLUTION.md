# Demo Tooling Evolution

How we iteratively built a full GPON network demo pipeline using AI-assisted development — from initial CSV generation to realistic geographic visualization across two target platforms.

> **Timeline:** 2026-02-24 to 2026-03-02 (8 working days)
> **Method:** Each phase was a conversation with Claude Code — describing the goal, reviewing generated code, and iterating on the result.

---

## Phase 1: Baseline Pipeline (Feb 24, morning)

**Goal:** Get a working end-to-end demo — generate synthetic GPON data, load it into both Kuwaiba and NetBox.

**What was built:**
- `generate_synthetic_data.py` — produces 8 CSV files from `config.yaml` definitions
- `kuwaiba_adapter.py` — SOAP/XML loader via zeep, creates containment hierarchy under Country → City
- `netbox_adapter.py` — REST/JSON loader via requests, creates device types, modules, cables
- `load_data.py` — CLI orchestrator with adapter pattern, dependency-ordered loading
- `run_demo.py` — single-command demo runner (`--target netbox|kuwaiba|both`)

**Key design decisions:**
- **CSV as intermediate format** — decouples generation from loading, enables manual inspection
- **Adapter pattern** — `BaseTargetAdapter` with `connect()`, `create_object()`, `create_connection()`, `verify_load()` so both targets share the same loader logic
- **Flattened Kuwaiba hierarchy** — splitters and ONTs go directly under City (not hierarchically under OLT) for demo simplicity

**Dataset:** 5 sites, 10 OLTs, 40 splitters, 200 ONTs, ~615 records total

```
d21d858  Initial commit: BMAD migration skills + GPON synthetic data demo
```

## Phase 2: Port Remapping & Docker Co-existence (Feb 24, early morning)

**Goal:** Run Kuwaiba and NetBox side by side on one machine.

**What changed:**
- Remapped Kuwaiba ports to 8880 (web) / 8881 (SOAP) to avoid conflict with NetBox on 8000

```
e45ba00  Remap Kuwaiba ports to 8880/8881 to allow parallel operation with NetBox
```

## Phase 3: OLT Internal Structure (Feb 24, afternoon)

**Goal:** Model realistic OLT chassis internals instead of flat device-with-ports.

**What was built:**
- Slot, Line Card (OLTBoard), and SFP Transceiver generation
- Per-vendor chassis definitions (Huawei MA5800: 18 slots, Nokia ISAM-FX16: 20 slots, ZTE C600: 16 slots)
- Port naming: `0/{slot}/{port}` matching real GPON conventions
- Kuwaiba containment: `OLT → Slot → OLTBoard → OpticalPort/Transceiver`
- NetBox modules: `DeviceType → ModuleBayTemplate → ModuleBay → Module → InterfaceTemplate`

**Key learning:** Kuwaiba 2.1 uses `OLTBoard` (subclass of GenericBoard), not `CommunicationsBoard`. NetBox `ModuleType` has no `slug` field — use `model` for lookups.

```
2ba3c07  Add structured OLT internals: slots, line cards, SFP transceivers
```

**Updated dataset:** 8 CSV files — sites, olts, slots, line_cards, splitters, sfp_transceivers, onts, connections

## Phase 4: Topology Visualization (Feb 28)

**Goal:** See the loaded GPON network on a map / topology view.

**What was built:**
- **Kuwaiba OSP View** — XML-based Outside Plant view with `<nodes>` (lat/lon) and `<edges>` (fiber connections) rendered on OpenStreetMap via `createOSPView` SOAP call
- **NetBox topology** — cable-based visualization using the netbox-topology-views plugin (auto-renders from existing Cable data, no extra API calls)
- Device placement: uniform ring offsets around site center (OLTs at 0.001deg, splitters at 0.003deg, ONTs at 0.006deg)

**Problem identified:** All devices of the same type form a perfect circle — unrealistic, but functional for first demo.

```
f104aaa  Add topology visualization for both NetBox and Kuwaiba targets
```

## Phase 5: Demo Scope Configurator (Feb 28)

**Goal:** Support multiple demo sizes without editing config files. Enable 2-level splitter cascades for more complex topologies.

**What was built:**
- `config_resolver.py` — layered config merge: base → preset → region → CLI
- Five presets with independent size/depth/complexity dimensions:

| Preset | Sites | OLTs | Splitters | ONTs | Cascade | ~Records |
|--------|-------|------|-----------|------|---------|----------|
| `minimal` | 1 | 1 | 2 | 8 | 1-level | 30 |
| `small` | 5 | 10 | 40 | 200 | 1-level | 615 |
| `medium` | 10 | 30 | 120 | 960 | 2-level | 2,000 |
| `large` | 20 | 80 | 400 | 3,200 | 2-level | 8,000 |
| `stress-test` | 50 | 200 | 1,200 | 12,000 | 2-level | 35,000 |

- Three region profiles: `czech` (default), `bratislava`, `vienna` — each with local city names, lat/lng bounds, and vendor preferences
- `generate_cascade_splitters()` — L1 splitter → L2 splitter hierarchy (40% cascade ratio for medium+ presets)
- Complexity knobs: `vendor_mode` (single/multi), `ont_model_variety` (low/normal), `failure_rate_percent` (0–15%)
- Skill 10 definition with usage guide and example chat transcript

```
ca569ce  Add Skill 10: Demo Scope Configurator with preset profiles and 2-level cascade
e1c8275  Add example demo chat to Skill 10 usage guide
```

**CLI examples after this phase:**
```bash
python run_demo.py --preset minimal --target netbox           # smoke test
python run_demo.py --preset medium --region bratislava --target kuwaiba  # regional demo
python run_demo.py --preset stress-test --generate-only       # data inspection
```

## Phase 6: Realistic Geo-Coordinates (Mar 1)

**Goal:** Devices should appear at realistic geographic positions on Kuwaiba's OSP map — OLTs clustered at CO sites, splitters spread into the service area, ONTs scattered around splitters.

**What was built:**
- `_offset_coord(lat, lng, distance_km, bearing_deg)` — flat-Earth bearing+distance offset (1deg lat ~ 111km, adjusted for longitude)
- Per-device lat/lng columns in CSV output:

| Device | Distance from parent | Placement logic |
|--------|---------------------|----------------|
| OLT | 10–50m from site | CO building jitter |
| L1 Splitter | 0.5–3km from site | Street cabinet in service area |
| L2 Splitter | 0.2–1km from L1 splitter | Distribution point |
| ONT | 0.1–1km from parent splitter | Customer premises |

- Kuwaiba adapter updated: reads per-device lat/lng from CSV if present, falls back to uniform ring layout for backward compatibility
- `load_data.py` now passes device CSV rows to `create_visualization()`

```
d5ffb31  Add realistic per-device geo-coordinates for GPON demo
```

## Phase 7: CFS/RFS Service Inventory — Kuwaiba (Mar 1)

**Goal:** Model customer-facing services (CFS) and resource-facing services (RFS) on top of the physical GPON layer. Kuwaiba has a native Service Manager module — use it.

**What was built:**
- `generate_synthetic_data.py` extended with `--include-services` flag — produces 4 additional CSV files:

| CSV | Content | Records (small preset) |
|-----|---------|----------------------|
| `subscribers.csv` | Customer per ONT (name, address, contract date, status) | 160 |
| `services_cfs.csv` | Broadband CFS per subscriber (tier, bandwidth, status) | 160 |
| `services_rfs.csv` | PON path RFS per CFS (VLAN, OLT→SPL→ONT path, status) | 160 |
| `service_resource_links.csv` | RFS↔device associations (ONT, OLT, splitter, port) | 640 |

- `kuwaiba_adapter.py` — new `load_services()` method using native SOAP Service Manager:
  - Creates customer pool → individual customers (1 per subscriber)
  - Creates CFS under customer → RFS under CFS
  - Links RFS to physical devices via `relateObjectToService()`
- `load_data.py` — hooks service loading after physical layer, guarded by CSV existence

**Key learning:** Kuwaiba's `createCustomer` and `createService` SOAP methods use different parameter ordering than `createObject`. The service class names (`GPONBroadbandCFS`, `GPONAccessRFS`) must first be added to the data model via `createClassLevelProperty`.

```
be95dfc  Add CFS/RFS service inventory prototype for Kuwaiba demo
28ff937  Fix SOAP method signatures for Kuwaiba Service Manager API
```

## Phase 8: CFS/RFS Service Inventory — NetBox via Custom Objects (Mar 1–2)

**Goal:** Bring the same CFS/RFS model to NetBox. NetBox has no native service module, but the [Custom Objects plugin](https://github.com/netboxlabs/netbox-custom-objects) (v0.4.6) allows defining new entity types and fields via REST API — no Django code needed.

**What was built:**
- `netbox_adapter.py` — `setup_service_model()` creates 3 Custom Object types with fields:

| Type | Key fields | FK references |
|------|-----------|---------------|
| `gpon_subscriber` | subscriber_id, customer_name, address, status | `ont_device` → dcim.device |
| `gpon_broadband_cfs` | cfs_id, service_tier (choice set), bandwidth, status | `subscriber_pk` (integer) |
| `gpon_access_rfs` | rfs_id, vlan_id, pon_path, status | `ont_device`, `olt_device`, `splitter_device` → dcim.device; `cfs_pk` (integer) |

- Choice sets via NetBox core API: `service_status` (ordered/provisioning/active/suspended/terminated) and `service_tier` (basic/standard/premium/ultra)
- `load_services()` — reads the same CSVs as Kuwaiba, creates subscribers → CFS → RFS
- Docker image upgraded from NetBox v4.2 to v4.4 (required by Custom Objects plugin)
- `netbox-topology-views` plugin upgraded from 4.2.0 to 4.4.0

**Bugs discovered in Custom Objects plugin (v0.4.6):**

1. **Cross-type FK fields break the dynamic model.** Defining an `object` field from one Custom Object type to another (e.g., CFS → Subscriber) creates the DB column and FK constraint correctly, but the Django dynamic model class (`Table2Model`) never registers the attribute. Any request to the type's instance endpoint returns `500: Table2Model() got unexpected keyword arguments`. **Workaround:** Use `integer` fields (`subscriber_pk`, `cfs_pk`) to store raw PKs instead of `object` FK fields. FK references to core Django models (e.g., `dcim.device`) work fine.

2. **Dynamic model cache is per-worker and stale after field creation.** NetBox runs on NGINX Unit with multiple application workers. When `setup_service_model()` creates fields via the REST API, only the worker handling that request updates its in-memory model. Other workers keep the old model without the new fields, causing `500: Table1Model() got unexpected keyword arguments` for any field added after the type was first used. **Fix:** Restart NGINX Unit workers after field setup via `docker exec netbox curl -s --unix-socket /opt/unit/unit.sock http://localhost/control/applications/netbox/restart`, then wait for health.

3. **List API ignores all query parameter filters.** Requesting `/api/plugins/custom-objects/custom-object-types/?slug=gpon-subscriber` returns all types, not just the matching one. Same for field filtering by `name` or `custom_object_type_id`. **Workaround:** Fetch all records (`?limit=100`) and filter client-side.

**Key takeaway:** Custom Objects is excellent for no-code entity definition and works well for FK references to built-in NetBox models. But cross-type references between custom types hit a fundamental plugin limitation — the dynamic Django model builder doesn't resolve inter-table ForeignKeys. For a demo, storing raw PKs in integer fields is a pragmatic workaround. For production, a full NetBox plugin with explicit Django models would be needed.

```
a70030a  Add CFS/RFS service inventory support for NetBox via Custom Objects plugin
b2f1222  Fix NetBox Custom Objects service loading (1013/1013, 0 errors)
```

**Updated dataset (small preset with `--include-services`):**
```
Entity             Success     Errors
------------------------------------------------------------
site                     5          0
olt                     10          0
slot                    39          0
line_card               39          0
splitter                40          0
sfp_transceiver         40          0
ont                    160          0
connection             200          0
subscriber             160          0
cfs                    160          0
rfs                    160          0
------------------------------------------------------------
TOTAL                 1013          0
```

**CLI examples after this phase:**
```bash
# Kuwaiba with native Service Manager
python run_demo.py --preset small --target kuwaiba --include-services

# NetBox with Custom Objects plugin
python run_demo.py --preset small --target netbox --include-services

# Both targets, services enabled
python run_demo.py --preset small --target both --include-services
```

## Phase 9: Rack Support & Physical Hierarchy (Mar 2)

**Goal:** OLTs in real GPON deployments sit inside racks in central office equipment rooms. Add racks to give the demo a realistic physical layout — and unlock NetBox's rack elevation view (a front/rear diagram showing devices stacked at U positions).

**What was built:**
- `value_pools.py` — added `u_height` per OLT vendor: Huawei MA5800-X15 (6U), Nokia ISAM-FX16 (5U), ZTE C600 (4U)
- `generate_synthetic_data.py` — new `generate_racks()` function:
  - Each site gets `ceil(olts_at_site / max_olts_per_rack)` racks (42U standard)
  - OLTs assigned to racks round-robin within their site
  - U-positions calculated bottom-up with 1U gap between devices
  - New `racks.csv` output + `rack_id`/`rack_position` columns added to `olts.csv`
- `netbox_adapter.py` — `_create_rack()` method, `u_height` on OLT device types, rack/position/face on device creation payload
- `kuwaiba_adapter.py` — extended containment: City → Building → Room → Rack → OLT. New `_ensure_building_room()` creates the intermediate hierarchy per site. Splitters and ONTs remain under City (field-deployed).
- `load-config.yaml` + `config.yaml` + `load_data.py` — rack entity in load order, mapping, and parent resolution

**Demo highlights:**
- **NetBox Rack Elevation:** Navigate to `/dcim/racks/<id>/` → Elevation tab shows OLTs stacked at their U positions with correct heights, color-coded by role, click-through to ports and cables
- **Kuwaiba Physical Tree:** Navigation tree shows City → Building → Equipment Room → R01 → OLT → Slot → Board → Port — the standard telecom physical hierarchy

**Bugs discovered and fixed:**

1. **NetBox bulk API response ordering.** `_bulk_create_sites()` originally used `zip(source_ids, results)` assuming positional correspondence between the request array and the response array. NetBox's bulk POST returns results in **non-deterministic order**, causing site ID mismatches that cascaded into "Rack R01 does not belong to site X" errors for OLTs placed in racks at the wrong site. **Fix:** Match results by unique field (slug for sites, name for devices, module_bay for line cards, label for SFPs) instead of position. Applied across all four bulk creation methods.

2. **Kuwaiba entity name/ID resolution collision.** After adding `rack_name`/`rack_id` attributes, the cascading `or` chain for resolving `obj_name` and `source_id` (`attributes.get("site_name") or attributes.get("rack_name") or attributes.get("olt_id") or ...`) caused OLTs to pick up `rack_id` as their display name (e.g., "RACK-SITE-0002-01" instead of "OLT-SITE-0001-01"). This also corrupted `_device_city_map`, breaking city resolution for all 200 splitters and ONTs. **Fix:** Replace the cascading `or` chain with an entity-type-specific field lookup dict — each entity type declares its own `(name_field, id_field)` pair.

**Key learning:** Bulk API response ordering is a silent assumption that works by coincidence in small test cases but breaks at scale when database insert order doesn't match request order. The fix — match by a unique business key — is simple but non-obvious until a real multi-site dataset exposes the mismatch.

```
376956c  Add rack support to GPON demo (Site → Rack → OLT physical hierarchy)
```

**Updated dataset (small preset with `--include-services`):**
```
Entity             Success     Errors
------------------------------------------------------------
site                     5          0
rack                     5          0
olt                     10          0
slot                    39          0
line_card               39          0
splitter                40          0
sfp_transceiver         40          0
ont                    160          0
connection             200          0
subscriber             160          0
cfs                    160          0
rfs                    160          0
service_link           640          0
------------------------------------------------------------
NetBox TOTAL          1018          0
Kuwaiba TOTAL         1658          0
```

---

## Architecture Overview

```
run_demo.py
  │
  ├── config_resolver.py ──→ merge base + preset + region + CLI
  │
  ├── generate_synthetic_data.py
  │     ├── value_pools.py (vendor/model/chassis/u_height data)
  │     └── output: 9 physical CSVs + 4 service CSVs (--include-services)
  │
  ├── Docker reset (compose down -v / up -d)
  │
  └── load_data.py
        ├── kuwaiba_adapter.py (SOAP, OSP View, Service Manager)
        ├── netbox_adapter.py  (REST, topology plugin, Custom Objects)
        └── id_mapping: source_id → target OID (thread-safe)
```

## Key Takeaways

1. **Iterate on real output.** Each phase was driven by looking at what the previous phase produced — screenshots of the OSP map revealed the ring layout problem, which led to Phase 6.

2. **CSV as the lingua franca.** Keeping CSV as the intermediate format between generation and loading made debugging trivial — `head -2 splitters.csv` instantly shows whether coordinates are present.

3. **Backward-compatible extensions.** New columns (lat/lng) and new parameters (device_rows) were added with fallbacks so older data still works.

4. **Layered configuration beats monolithic configs.** Separating size, depth, complexity, and region into independent dimensions keeps presets small and composable.

5. **Adapter pattern pays off early.** Supporting two radically different targets (SOAP/XML vs. REST/JSON) with one loader proved the abstraction from day one.

6. **AI-assisted != AI-automated.** Each phase required reviewing generated code, catching API quirks (OLTBoard vs CommunicationsBoard, ModuleType lacking slug), and steering the next iteration based on real-world testing against Docker containers.

7. **Plugin bugs surface only at runtime.** The Custom Objects plugin passed basic smoke tests but revealed three distinct bugs (cross-type FK, model cache staleness, broken filters) only when the full service loading pipeline ran end-to-end. The fix cycle — read error, form hypothesis, test via curl, implement workaround — is inherently interactive and hard to automate away.

8. **Same data, different targets, different trade-offs.** Kuwaiba's native Service Manager gives proper CFS/RFS lifecycle with `relateObjectToService`. NetBox's Custom Objects gives no-code flexibility but lacks cross-type FK support. The adapter pattern absorbs this difference — the CSV format and `load_services()` contract are identical for both.

9. **Never assume API response ordering.** Bulk POST endpoints may return results in a different order than the request array. Matching by position works by coincidence with small datasets but breaks silently at scale. Always match by a unique business key (slug, name, serial) — it's one extra dict lookup but prevents an entire class of subtle data corruption bugs.
