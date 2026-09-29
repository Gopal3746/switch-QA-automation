# Injected Defect Reports

These defects are deliberately introduced into the simulated topology to demonstrate detection, diagnosis, and recovery. They are not reports of defects in NVIDIA products.

## DEF-001: Missing trunk VLAN

| Field | Value |
|---|---|
| Detected by | TC-09 |
| Component | `switch2` trunk port `swp1` |
| Severity | High |
| Expected | VLANs 10 and 20 allowed |
| Actual | Only VLAN 20 allowed |
| User impact | VLAN 10 traffic cannot cross the inter-switch trunk |

### Reproduction

1. Create the topology using the `buggy` simulation scenario.
2. Query allowed VLANs on `switch2.swp1`.
3. Compare the returned VLAN set with `{10, 20}`.
4. Observe that VLAN 10 is missing.

### Root cause

The injected topology state omits VLAN 10 from the allowed VLAN membership of the `switch2` trunk. Although both access hosts belong to VLAN 10, frames for that VLAN cannot traverse the complete inter-switch path.

### Diagnostic evidence

Relevant evidence includes:

```text
nv show interface swp1
bridge vlan show
ip link
ip route
ping
```

### Corrective action

Restore VLAN 10 to the trunk's allowed VLAN set, apply the configuration, and save it so the corrected state survives reload.

### Verification

- TC-02 and TC-03 confirm expected trunk membership.
- TC-07 confirms end-to-end connectivity.
- TC-13 confirms recovery after both injected defects are corrected.

---

## DEF-002: Incorrect access-port PVID

| Field | Value |
|---|---|
| Detected by | TC-10 |
| Component | `switch1` access port `swp1` |
| Severity | High |
| Expected | PVID 10 |
| Actual | PVID 20 |
| User impact | Host A traffic is classified into the wrong VLAN |

### Reproduction

1. Create the topology using the `buggy` simulation scenario.
2. Query the PVID assigned to `switch1.swp1`.
3. Compare the value with the expected engineering VLAN.
4. Observe PVID 20 instead of PVID 10.

### Root cause

The access port connected to Host A is deliberately assigned to the management VLAN instead of the engineering VLAN. Untagged traffic from Host A is therefore classified incorrectly.

### Diagnostic evidence

Relevant evidence includes:

```text
nv show interface swp1
bridge vlan show
ip link
ip route
ping
```

### Corrective action

Restore the access-port PVID to VLAN 10, apply the configuration, and save the corrected state.

### Verification

- TC-01 validates the access-port PVID.
- TC-07 validates same-VLAN connectivity.
- TC-13 corrects both defects and confirms connectivity recovery.

## Negative connectivity scenario

TC-11 administratively disables the access port and verifies:

- The destination is unreachable.
- Zero packets are received.
- Packet loss is 100 percent.

This prevents the framework from reporting a false connectivity pass when the access link is unavailable.
