# Cumulus Switch QA Automation
[![Switch QA](https://github.com/Gopal3746/switch-QA-automation/actions/workflows/qa-tests.yml/badge.svg)](https://github.com/Gopal3746/switch-QA-automation/actions/workflows/qa-tests.yml)
A Python and Pytest framework for validating VLAN configuration, switch-port
state, and end-to-end connectivity across a two-switch Cumulus Linux topology.

The framework will support:

- A simulated Cumulus/NVUE backend for local development and CI
- A Paramiko-based SSH backend for compatible lab switches
- Requirement-linked functional, regression, and negative tests
- Automatic diagnostic evidence and test summary reports

## Development setup

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -e ".[dev]"
pytest
