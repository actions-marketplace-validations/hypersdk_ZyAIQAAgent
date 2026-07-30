---
title: HyperSDK VMware Migration Workflow
product: HyperSDK
version: "1.0"
source: migration-guide
url: https://zyvor.dev/docs/customer-manuals
tenant_id: public
access_level: public
updated_at: "2026-07-30"
---

# HyperSDK VMware Migration Workflow

## Discovery

Collect the VMware inventory, including virtual machines, networks, datastores,
snapshots, guest operating systems, firmware type and attached devices. Migration
planning should identify unsupported devices, stale snapshots, encrypted disks and
guest-driver requirements before conversion.

## Conversion

hyper2kvm converts supported VMware virtual disks for KVM-based targets. The workflow
can inject VirtIO drivers, inspect the guest, repair boot configuration and validate
the converted disk. A conversion result should not be treated as production-ready
until the guest boots and its network, storage and application services are tested.

## Validation

Use a test migration before the production cutover. Validate boot, IP configuration,
DNS, application ports, service startup, storage mounts and performance. Retain a
rollback path until business acceptance is complete.
