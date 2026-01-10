#!/usr/bin/env python3
"""
Build Arista EOS configs using:
- An Ansible inventory file (YAML/INI)
- group_vars/ (and host_vars/) directories
- PyAVD (eos_designs -> eos_cli_config_gen)

Requires:
  pip install "pyavd[ansible]"  (or install ansible-core separately)
"""

from __future__ import annotations
import json 
from pprint import pprint
import argparse
from pathlib import Path

from ansible.parsing.dataloader import DataLoader
from ansible.inventory.manager import InventoryManager
from ansible.vars.manager import VariableManager

from pyavd.validate_inputs import validate_inputs
from pyavd.get_avd_facts import get_avd_facts
from pyavd.get_device_structured_config import get_device_structured_config
from pyavd.validate_structured_config import validate_structured_config
from pyavd.get_device_config import get_device_config


def strip_ansible_noise(all_vars: dict) -> dict:
    """
    Keep this simple: drop obvious Ansible/internal keys.
    You can tighten this further if you want to be strict.
    """
    drop_prefixes = ("ansible_",)
    drop_exact = {
        "groups",
        "group_names",
        "hostvars",
        "inventory_dir",
        "inventory_file",
        "inventory_hostname",
        "inventory_hostname_short",
        "playbook_dir",
        "omit",
    }

    cleaned = {}
    for k, v in all_vars.items():
        if k in drop_exact:
            continue
        if any(k.startswith(p) for p in drop_prefixes):
            continue
        cleaned[k] = v
    return cleaned


def main() -> None:
    parser = argparse.ArgumentParser(description="Build EOS configs with Ansible inventory + group_vars + PyAVD")
    parser.add_argument("-i", "--inventory", required=True, help="Path to Ansible inventory file (yaml/ini)")
    parser.add_argument(
        "--basedir",
        default=None,
        help="Base directory for Ansible var loading (defaults to inventory directory). "
             "Put group_vars/ and host_vars/ under this directory.",
    )
    parser.add_argument("-o", "--output-dir", default="outputs", help="Where to write *.cfg files")
    args = parser.parse_args()

    inventory_path = Path(args.inventory).resolve()
    if not inventory_path.exists():
        raise SystemExit(f"Inventory not found: {inventory_path}")

    basedir = Path(args.basedir).resolve() if args.basedir else inventory_path.parent
    output_dir = Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    # --- Load inventory + vars using Ansible ---
    loader = DataLoader()
    loader.set_basedir(str(basedir))

    inventory = InventoryManager(loader=loader, sources=[str(inventory_path)])
    var_manager = VariableManager(loader=loader, inventory=inventory)

    # Build all_inputs dict[str, dict] for pyavd.get_avd_facts()
    # (keys are hostnames, values are eos_designs inputs per device) :contentReference[oaicite:1]{index=1}
    all_inputs: dict[str, dict] = {}

    for host in inventory.get_hosts():
        hostname = host.get_name()
        host_vars = var_manager.get_vars(host=host)
        inputs = strip_ansible_noise(host_vars)

        # Ensure hostname is present for AVD logic
        inputs.setdefault("hostname", hostname)

        # Validate/convert eos_designs inputs in-place :contentReference[oaicite:2]{index=2}
        validation = validate_inputs(inputs)
        if validation.failed:
            raise SystemExit(f"[{hostname}] eos_designs input validation failed:\n{validation}")

        all_inputs[hostname] = inputs

    # --- Build shared AVD facts once for the whole fabric --- :contentReference[oaicite:3]{index=3}
    avd_facts = get_avd_facts(all_inputs)
    pprint(avd_facts)
    # --- Build per-host structured_config and render CLI config --- :contentReference[oaicite:4]{index=4}
    for hostname, inputs in all_inputs.items():
        structured_config = get_device_structured_config(hostname, inputs, avd_facts)

        sc_validation = validate_structured_config(structured_config)
        if sc_validation.failed:
            raise SystemExit(f"[{hostname}] structured_config validation failed:\n{sc_validation}")

        eos_cli_config = get_device_config(structured_config)

        out_file = output_dir / f"{hostname}.cfg"
        out_file.write_text(eos_cli_config, encoding="utf-8")
        print(f"Wrote {out_file}")

    print("Done.")


if __name__ == "__main__":
    main()
