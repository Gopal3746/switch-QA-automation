# 13-Case Switch QA Test Plan

## Objective

Validate VLAN configuration, port behavior, connectivity, configuration persistence, negative conditions, and recovery across the two-switch topology.

## Execution environments

| Environment | Purpose |
|---|---|
| Simulated | Complete deterministic functional, negative, and regression execution |
| Live SSH | Non-destructive VLAN and connectivity validation against lab switches |
| GitHub Actions | Automated simulated regression execution on every change |

## Test cases

| ID | Area | Category | Requirement | Backend |
|---|---|---|---|---|
| TC-01 | VLAN | Functional | Access ports must use engineering VLAN 10 | Both |
| TC-02 | VLAN | Functional | Switch1 trunk must carry VLANs 10 and 20 | Both |
| TC-03 | VLAN | Functional | Switch2 trunk must carry VLANs 10 and 20 | Both |
| TC-04 | VLAN | Security | Hosts in different VLANs must remain isolated | Both |
| TC-05 | Port state | Functional | Administrative state changes must be observable | Simulated |
| TC-06 | Port state | Functional | Trunk operational state must reflect peer availability | Simulated |
| TC-07 | Connectivity | Functional | Hosts in VLAN 10 must have end-to-end connectivity | Both |
| TC-08 | Connectivity | Performance | Packet loss must remain at or below one percent | Both |
| TC-09 | VLAN | Negative | Detect a missing required trunk VLAN | Simulated |
| TC-10 | VLAN | Negative | Detect an incorrect access-port PVID | Simulated |
| TC-11 | Connectivity | Negative | A down access port must prevent connectivity | Simulated |
| TC-12 | Persistence | Regression | Saved configuration must survive reload | Simulated |
| TC-13 | Recovery | Regression | Connectivity must recover after both defects are corrected | Simulated |

## Entry criteria

- Project dependencies are installed.
- `configs/topology.yaml` passes schema and relationship validation.
- The simulated backend is available, or both lab switches are reachable through SSH.
- Required SSH environment variables are configured for live execution.
- Live switch host keys are present in `known_hosts`.

## Exit criteria

- All 13 cases pass in the simulated regression suite.
- No Ruff violations remain.
- The test-to-requirement matrix contains one mapping for every QA case.
- JSON and Markdown summaries are generated.
- Failure evidence is captured for any failed requirement-linked case.
- GitHub Actions completes successfully.

## Commands

Run the complete project suite:

```bash
python -m pytest
```

Run the simulated QA plan:

```bash
python -m pytest tests/qa --backend=simulated -v
```

Run safe checks through SSH:

```bash
python -m pytest tests/qa --backend=ssh -v
```

Run linting and coverage:

```bash
python -m ruff check .

python -m pytest \
  --cov=switch_qa \
  --cov-report=term-missing \
  --cov-report=xml \
  --junitxml=reports/junit.xml
```

## Evidence

On failure, evidence may include:

- NVUE interface state
- Linux link state
- Bridge VLAN membership
- Routing information
- Ping reachability and packet loss
- Pytest failure details

Execution summaries are written to `reports/summary.json` and `reports/summary.md`.
