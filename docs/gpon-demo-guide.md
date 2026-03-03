# GPON Migration Demo Guide

> Presenter playbook for demonstrating synthetic GPON data migration into
> **NetBox** (REST) and **Kuwaiba** (SOAP).

## What You Are Demonstrating

A BMAD skill-generated pipeline that:

1. **Generates** realistic GPON access-network data (sites, OLTs, splitters, ONTs, fiber connections)
2. Optionally generates **CFS/RFS service inventory** (subscribers, broadband tiers, PON path services, resource links)
3. **Loads** that data into a target inventory system via its native API
4. **Verifies** the result in the target's UI

The audience sees the full generate-transform-load cycle running against real
software, not slides.

### Data at a Glance

```
Site (5)
 ├─ Rack (~10)            42U standard racks in equipment room
 │   └─ OLT (10)          Huawei MA5800-X15 (6U) / Nokia ISAM-FX16 (5U) / ZTE C600 (4U)
 │       ├─ Slot (~40)    Chassis slot positions (2-4 GPON + 1 control per OLT)
 │       │   └─ Line Card (~40)  H901GPHF, FGLT-B, GFGL, etc.
 │       │       └─ SFP (~40)    B+/C+/C++ transceivers on connected ports
 │       └─ Splitter (40)     1:8, 1:16, 1:32 passive optical splitters (field-deployed)
 └─ ONT (200)             HG8245H, HG8546M, F660, I-010G-Q (customer premises)
Fiber connections: 240    (OLT↔splitter + splitter↔ONT, single-mode fiber)
Port naming: 0/{slot}/{port}  (shelf/slot/port — real vendor CLI format)
```

| Entity          | Count | Example ID                  | Key Fields                           |
|-----------------|------:|-----------------------------|------------------------------------- |
| Site            |     5 | `SITE-0001`                 | Prague Central CO, 49.34N 14.12E     |
| Rack            |   ~10 | `RACK-SITE-0001-01`         | R01, 42U, equipment room             |
| OLT             |    10 | `OLT-SITE-0001-01`          | Nokia ISAM-FX16, serial ALCI39C0CB52 |
| Slot            |   ~40 | `SLOT-OLT-SITE-0001-01-03`  | Slot 3, service type                 |
| Line Card       |   ~40 | `CARD-SLOT-OLT-SITE-0001-01-03` | H901GPHF, 16 ports             |
| SFP Transceiver |   ~40 | `SFP-CARD-...-01`           | C+, 1490/1310nm                      |
| Splitter        |    40 | `SPL-OLT-SITE-0001-01-01`   | 1:16, port 0/3/1                     |
| ONT             |   200 | `ONT-000001`                | I-010G-Q, Nokia, CUST-CA7330B0507E   |
| Connection      |   240 | `CONN-000001`               | smf, 0/3/1 ↔ input                   |

---

## Part 1 — Common Setup (both targets)

### 1.1 Prerequisites

| What               | Why                                    |
|--------------------|----------------------------------------|
| Python 3.10+       | Runs all scripts                       |
| Docker + Compose   | Hosts the target system                |
| `pip install pyyaml` | YAML config parsing (optional — built-in fallback exists) |
| `pip install requests` | NetBox REST adapter                 |
| `pip install zeep`    | Kuwaiba SOAP adapter                |

### 1.2 Generate Synthetic Data

This step is the same regardless of target. Run it once.

```bash
python staging/scripts/synthetic/generate_synthetic_data.py \
  --config staging/scripts/synthetic/config.yaml \
  --output-dir staging/scripts/synthetic/output \
  --seed 42
```

Expected output:

```
Done. ~615 rows written to staging/scripts/synthetic/output/
  sites.csv: 5 rows
  olts.csv: 10 rows
  slots.csv: ~40 rows
  line_cards.csv: ~40 rows
  splitters.csv: 40 rows
  sfp_transceivers.csv: ~40 rows
  onts.csv: 200 rows
  connections.csv: 240 rows
```

**Talking points while it runs:**

- The config defines entity volumes and attribute distributions (vendor weights, status ratios)
- Seed 42 means fully deterministic — re-run produces identical data
- IDs encode the hierarchy: `SPL-OLT-SITE-0001-01-01` tells you which OLT and site
- OLT internals use real vendor models: Huawei H901GPHF, Nokia FGLT-B, ZTE GFGL line cards
- Port naming follows real CLI format: `0/{slot}/{port}` (shelf/slot/port)
- `manifest.json` has SHA-256 checksums for audit traceability

**Optional: show the CSVs**

```bash
# Show sites
column -t -s, staging/scripts/synthetic/output/sites.csv

# Show first few OLTs
head -6 staging/scripts/synthetic/output/olts.csv | column -t -s,
```

### 1.3 Dry Run (optional, good for walkthrough)

Before hitting a real target, show the loader in dry-run mode:

```bash
python staging/scripts/load/load_data.py \
  --adapter netbox \
  --config staging/scripts/load/load-config.yaml \
  --data-dir staging/scripts/synthetic/output \
  --dry-run
```

The summary table shows ~615 total / 0 errors without any API calls.

---

## Part 2 — NetBox Playbook

### 2.1 Start NetBox

```bash
docker compose -f scripts/docker-compose.netbox.yml up -d
```

First startup takes ~60 seconds (PostgreSQL migrations + superuser creation).
Wait until the health endpoint responds:

```bash
# Poll until ready
TOKEN="0123456789abcdef0123456789abcdef01234567"
until curl -sf http://localhost:8000/api/status/ -H "Authorization: Token $TOKEN" > /dev/null; do
  echo "Waiting for NetBox..."; sleep 5
done
echo "NetBox is ready."
```

### 2.2 Load Data

```bash
python staging/scripts/load/load_data.py \
  --adapter netbox \
  --config staging/scripts/load/load-config.yaml \
  --data-dir staging/scripts/synthetic/output
```

Or use the one-command orchestrator:

```bash
python staging/demo/run_demo.py --target netbox
```

**What happens under the hood (walk the audience through the log):**

1. **Model setup** — adapter creates:
   - Tag `gpon-migration` (for filtering demo data later)
   - Custom fields `source_id` and `serial_number` on devices and sites
   - Manufacturers: Huawei, Nokia, ZTE, Generic
   - Device roles: OLT, Splitter, ONT (colour-coded)
   - OLT DeviceTypes with ModuleBayTemplates (slot positions)
   - ModuleTypes for GPON cards (H901GPHF, FGLT-B, GFGL, etc.) with InterfaceTemplates
   - ModuleTypes for control cards (H901MPLA, FANT-F, SFUH) with uplink InterfaceTemplates
   - InventoryItemRole "SFP Transceiver"
   - Splitter/ONT DeviceTypes with direct InterfaceTemplates
2. **Sites** — 5 sites created as NetBox Sites with coordinates
3. **Racks** — ~10 racks created (42U standard) at each site
4. **OLTs** — 10 OLTs created with rack placement (U position + face) — visible in rack elevation view
4. **Slots** — ~40 ModuleBays found by position on each OLT
5. **Line Cards** — ~40 Modules installed into ModuleBays (interfaces auto-created from ModuleType templates)
6. **Splitters** — 40 splitter devices
7. **SFP Transceivers** — ~40 InventoryItems on OLT devices
8. **ONTs** — 200 ONT devices
9. **Cables** — 240 SMF connections between interfaces

### 2.3 Navigate the GPON Network in NetBox

Open **http://localhost:8000** — login `admin` / `admin`.

#### Start at a Site

1. **DCIM > Sites** — 5 sites listed (Prague Central CO, Brno South CO, …)
2. Click **Prague Central CO**
3. Scroll to the **Racks** tab — you see racks (R01, R02) with OLTs installed
4. Scroll to the **Devices** tab — you see 2 OLTs, 8 splitters, 40 ONTs at this site

#### Rack Elevation View (highlight feature)

1. **DCIM > Racks** — list of all racks across sites
2. Click any rack (e.g., **R01** at Prague Central CO)
3. Click the **Elevation** tab — front/rear diagram shows:
   - OLTs stacked at their U positions (Huawei 6U, Nokia 5U, ZTE 4U)
   - Color-coded by device role
   - Click any OLT in the elevation → jumps to device details (ports, cables, modules)
4. This view is auto-generated from the rack position data — no manual layout needed

#### Trace: Site → Rack → OLT → Module Bay → Module → Interface → Splitter → ONT

1. From Prague Central CO devices, click OLT **OLT-SITE-0001-01**
2. Go to the **Module Bays** tab — see slot positions (Slot 1, Slot 3, …)
3. Click an installed module (e.g., **H901GPHF** in Slot 3)
4. Go to the module's **Interfaces** tab — 16 GPON ports (`0/3/1` … `0/3/16`)
5. Click **0/3/1** — the cable panel shows it connects to **SPL-OLT-SITE-0001-01-01 : input**
6. Click that splitter link — you're now on the splitter device
7. Go to its **Interfaces** tab — 1 `input` + numbered `output-1` … `output-N` ports
8. Click **output-1** — the cable connects to **ONT-000001 : pon**
9. Click that ONT link — you've traced the full path: **OLT → Line Card → Splitter → ONT**

#### View Inventory Items (SFP Transceivers)

1. On any OLT, go to the **Inventory** tab
2. See SFP transceivers listed with class (B+/C+/C++) and wavelength
3. Each SFP corresponds to a connected GPON port on a line card

#### Filter by Role

1. **DCIM > Devices** — shows all 250 devices
2. Use the **Role** filter:
   - **OLT** (10) — Huawei MA5800-X15, Nokia ISAM-FX16, ZTE C600
   - **SPLITTER** (40) — Generic Splitter-1xN
   - **ONT** (200) — mixed HG8245H, HG8546M, F660, I-010G-Q

#### View Cables

1. **DCIM > Cables** — 240 fiber connections listed
2. Click any cable to see both ends (e.g., `OLT-SITE-0001-01 : gpon-1` ↔ `SPL-OLT-SITE-0001-01-01 : input`)

### 2.4 Cleanup

```bash
docker compose -f scripts/docker-compose.netbox.yml down -v
```

---

## Part 3 — Kuwaiba Playbook

### 3.1 Start Kuwaiba

```bash
docker compose -f scripts/docker-compose.kuwaiba.yml up -d
```

Kuwaiba starts faster (~30 seconds). Wait until the WSDL endpoint responds:

```bash
until curl -sf http://localhost:8881/kuwaiba/KuwaibaService?wsdl > /dev/null; do
  echo "Waiting for Kuwaiba..."; sleep 5
done
echo "Kuwaiba is ready."
```

### 3.2 Load Data

```bash
python staging/scripts/load/load_data.py \
  --adapter kuwaiba \
  --config staging/scripts/load/load-config.yaml \
  --data-dir staging/scripts/synthetic/output
```

Or use the orchestrator:

```bash
python staging/demo/run_demo.py --target kuwaiba
```

**What happens under the hood:**

1. **SOAP session** — adapter creates an authenticated session via `createSession`
2. **Containment rules** — adds City→Building→Room→Rack→OLT, OLT→Slot→OLTBoard→Port
3. **Vendor list types** — creates EquipmentVendor entries (Huawei, Nokia, ZTE)
4. **Sites as Cities** — 5 City objects with Building→Room chains for rack placement
5. **Racks** — ~10 Rack objects under Equipment Rooms
6. **OLTs** — 10 OpticalLineTerminal objects under their assigned Rack
7. **Slots** — ~40 Slot objects inside OLTs
8. **Line Cards** — ~40 OLTBoard objects inside Slots (with OpticalPort children)
9. **Splitters** — 40 FiberSplitter objects under City (with input/output ports)
10. **SFP Transceivers** — ~40 Transceiver objects inside OLTBoards
11. **ONTs** — 200 OpticalNetworkTerminal objects under City (with pon port)
12. **Connections** — 240 OpticalLink physical connections between ports

### 3.3 Navigate the GPON Network in Kuwaiba

Open **http://localhost:8880/kuwaiba/home** — login `admin` / `kuwaiba`.

#### Start at the Containment Tree

1. In the left sidebar, open **Navigation** (or the tree browser)
2. Expand **GPON Demo** (Country) — you see 5 Cities:
   - Prague Central CO, Brno South CO, Ostrava Main CO, Plzen West CO, Liberec North CO

#### Trace: Country → City → Building → Room → Rack → OLT → Slot → Board → Port

1. Expand **Prague Central CO** — you see:
   - **Prague Central CO Building** (Building) — contains the equipment room
   - 8 FiberSplitters: `SPL-OLT-SITE-0001-01-01`, … (field-deployed, under City)
   - 40 OpticalNetworkTerminals (ONTs): `ONT-000001`, … (customer premises, under City)
2. Expand the **Building** → **Equipment Room** (Room) → **R01** (Rack)
3. Under the rack you see OLTs: `OLT-SITE-0001-01`, `OLT-SITE-0001-06`
4. Click **OLT-SITE-0001-01** — the property sheet shows:
   - Class: `OpticalLineTerminal`
   - Description: `Vendor: Nokia | Model: ISAM-FX16 | S/N: … | Status: IN_SERVICE`
5. Expand the OLT — it contains **Slot** children (Slot 3, Slot 7, …)
6. Expand a Slot — it contains an **OLTBoard** (line card)
7. Expand the board — it contains **OpticalPort** children (`0/3/1`, `0/3/2`, …) and optionally **Transceiver** objects
8. Click **0/3/1** — this is the port that connects to the splitter

#### View Connections

1. Expand a FiberSplitter (e.g., **SPL-OLT-SITE-0001-01-01**)
   - It contains OpticalPort children: `input`, `output-1` … `output-5`
2. Select the splitter or one of its ports
3. Open the **Connections** or **Physical Path** view (right panel or context menu)
   - You see the OpticalLink from OLT gpon-1 → splitter input
   - And OpticalLinks from splitter output-1…5 → ONT pon ports
4. Click an ONT (e.g., **ONT-000001**) — expand it to see its `pon` port

The full physical path: **City → Building → Equipment Room → Rack → OLT → Slot → OLTBoard → OpticalPort 0/3/1 → OpticalLink → Splitter input → Splitter output-1 → OpticalLink → ONT pon**

> **Note:** OLTs are placed inside Racks using the standard telecom physical hierarchy (City → Building → Room → Rack). Splitters and ONTs remain under City (field-deployed in street cabinets / customer premises). The logical GPON topology is captured via OpticalLink connections between ports.

### 3.4 Service Inventory (CFS/RFS) — Optional

The demo can also load **service inventory** into Kuwaiba's Service Manager module,
demonstrating the telecom-standard CFS/RFS pattern on top of the physical network.

```bash
# Generate + load with services
python staging/demo/run_demo.py --target kuwaiba --include-services

# Or generate services separately
python staging/scripts/synthetic/generate_synthetic_data.py \
  --config staging/scripts/synthetic/config.yaml \
  --output-dir staging/scripts/synthetic/output \
  --seed 42 --include-services
```

**What `--include-services` adds:**

| Entity               | Count | Description                                              |
|----------------------|------:|----------------------------------------------------------|
| Subscriber           |   200 | One per ONT (Czech names: Jan Novák, Eva Černý, …)     |
| CFS (Broadband)      |   200 | Customer-facing service tier (30/10 – 1000/300 Mbps)    |
| RFS (PON Path)       |   200 | Resource-facing service (VLAN, OLT→SPL→ONT path)       |
| Service-Resource Link |  ~800 | RFS → ONT, splitter, OLT, fiber connections             |

**CFS/RFS model in Kuwaiba:**

```
CustomerPool: "GPON Demo Customers"
  └─ Customer: "Jan Novák" (GenericCustomer)
      └─ ServicePool: "Services"
          ├─ CFS: "GPON Standard 100/50" (GPONBroadbandCFS)
          │     relates to → RFS
          └─ RFS: "PON Path ONT-000001" (GPONAccessRFS)
                relates to → ONT, OLT, Splitter, Fiber connections
```

**Navigate in Kuwaiba UI:**

1. Open **Service Manager** module (left sidebar → Service Manager)
2. Expand **GPON Demo Customers** pool — see 200 customers
3. Click a customer (e.g., **Jan Novák**) — expand **Services** pool
4. Two services visible: one **GPONBroadbandCFS** (tier + bandwidth) and one **GPONAccessRFS** (VLAN + PON path)
5. Select the RFS — the **Related Resources** panel shows linked ONT, splitter, OLT, and fiber connections
6. Right-click an ONT anywhere in the tree → **Affected Services** shows which CFS/RFS depend on it

**Talking points:**

- CFS = what the customer buys (tier, bandwidth). RFS = what the network provides (VLAN, path)
- 1:1 CFS↔RFS per ONT — simple for GPON; in production, one RFS can back multiple CFS (multiplay)
- `getAffectedServices` answers "if this ONT fails, which customers are impacted?" — built into Kuwaiba
- Custom classes (GPONBroadbandCFS, GPONAccessRFS) extend GenericService — created automatically via SOAP

### 3.5 Service Inventory in NetBox (Custom Objects) — Optional

NetBox can also model CFS/RFS services using the **Custom Objects** plugin
(no-code custom entity types defined via REST API at load time).

```bash
# Generate + load with services
python staging/demo/run_demo.py --target netbox --include-services
```

**CFS/RFS model in NetBox (Custom Objects):**

```
GPONSubscriber: "Jan Novák" (subscriber_id, ont_device → ONT)
  └─ GPONBroadbandCFS: "standard_100_50" (cfs_id, service_tier, bandwidth)
      └─ GPONAccessRFS: (rfs_id, vlan_id, pon_path)
            ont_device → ONT, olt_device → OLT, splitter_device → Splitter
```

**Navigate in NetBox UI:**

1. Open **Custom Objects** menu (left sidebar → Plugins → Custom Objects)
2. Click **GPONSubscriber** — see all subscribers with linked ONT devices
3. Click a subscriber (e.g., **Jan Novák**) — see ONT device link
4. Switch to **GPONBroadbandCFS** — see CFS records with service tier, bandwidth, subscriber link
5. Switch to **GPONAccessRFS** — each RFS shows linked CFS, OLT, splitter, and ONT devices
6. Click any linked device to navigate directly to the DCIM device page

**Lifecycle status:** Custom Objects uses a `select` choice field (`ordered`,
`provisioning`, `active`, `suspended`, `terminated`). All valid statuses can be
set and filtered, but transitions are not enforced (any status can change to
any other). For enforced state machines, a full NetBox plugin with Django
validation would be required.

### 3.6 Cleanup

```bash
docker compose -f scripts/docker-compose.kuwaiba.yml down -v
```

---

## Part 4 — Side-by-Side Comparison (optional)

If you have both targets running, show how the same data looks in each system.

```bash
# Load into both (data generation runs once, loading runs twice)
python staging/demo/run_demo.py --target both
```

### Comparison Table for the Audience

| Aspect                 | NetBox                               | Kuwaiba                              |
|------------------------|--------------------------------------|--------------------------------------|
| **API style**          | REST/JSON — stateless, token auth    | SOAP/XML — session-based, WSDL       |
| **Site model**         | Site (flat, with coordinates)        | City (graph node, containment root)  |
| **Device model**       | Device + DeviceType + Role           | Class hierarchy (OLT extends GenericCommunicationsElement) |
| **Port/interface**     | Interface (single type field)        | OpticalPort / ElectricalPort classes |
| **Connection model**   | Cable (A/B terminations)             | OpticalLink (physical connection)    |
| **Hierarchy enforcement** | None (foreign keys, flexible)     | Strict containment rules per class   |
| **Bulk operations**    | Native JSON array POST               | One-at-a-time SOAP calls             |
| **Custom attributes**  | Custom Fields (runtime)              | Class metadata (model-level)         |
| **Service inventory**  | Custom Objects plugin (CFS/RFS via `--include-services`) | Native Service Manager (CFS/RFS via `--include-services`) |
| **Idempotency**        | Check-then-create + 409 handling     | Fails on duplicate; fresh container for re-run |
| **UI**                 | Django web, REST API browser         | Vaadin web, SOAP client/SoapUI       |

### Key Narrative

> "Both systems received the exact same CSV data through the same abstract
> adapter interface. The adapter pattern means adding a third target
> (e.g., Device42, Ralph, i-doit) requires implementing one Python class —
> not rewriting the pipeline."

---

## Part 5 — Presenter Cheat Sheet

### One-Liner Commands

```bash
# Generate only
python staging/demo/run_demo.py --target netbox --generate-only

# NetBox full demo
python staging/demo/run_demo.py --target netbox

# Kuwaiba full demo
python staging/demo/run_demo.py --target kuwaiba

# Kuwaiba with CFS/RFS service inventory
python staging/demo/run_demo.py --target kuwaiba --include-services

# NetBox with CFS/RFS service inventory (Custom Objects plugin)
python staging/demo/run_demo.py --target netbox --include-services

# Both targets
python staging/demo/run_demo.py --target both

# Dry run (no target needed)
python staging/demo/run_demo.py --target netbox --dry-run
```

### Default Credentials

| System  | URL                        | Username | Password / Token                            |
|---------|----------------------------|----------|---------------------------------------------|
| NetBox  | http://localhost:8000      | admin    | admin (UI) / `0123456789abcdef...` (API)    |
| Kuwaiba | http://localhost:8880      | admin    | kuwaiba                                     |

### Common Issues During Demo

| Symptom                        | Fix                                                        |
|--------------------------------|------------------------------------------------------------|
| "netbox is not reachable"      | `docker compose -f scripts/docker-compose.netbox.yml up -d` — wait 60s |
| "kuwaiba is not reachable"     | `docker compose -f scripts/docker-compose.kuwaiba.yml up -d` — wait 30s |
| `401 Unauthorized` (NetBox)    | Token mismatch — check `load-config.yaml` vs `docker-compose.netbox.yml` |
| `Containment error` (Kuwaiba)  | Class not allowed as child — check Kuwaiba containment rules in admin UI |
| Duplicate devices on re-run    | `docker compose ... down -v && docker compose ... up -d` for fresh state |
| `ModuleNotFoundError: zeep`    | `pip install zeep` — only needed for Kuwaiba target         |
| `ModuleNotFoundError: requests`| `pip install requests` — only needed for NetBox target       |

### Timing Expectations

| Step                     | Duration       |
|--------------------------|--------------- |
| Data generation          | < 1 second     |
| NetBox full load         | ~100 seconds   |
| Kuwaiba full load        | ~10 seconds    |
