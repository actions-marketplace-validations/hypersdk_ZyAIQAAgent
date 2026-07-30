---
title: GuestKit disk inspection overview
product: GuestKit
version: "1.0"
source: customer-manual
url: https://zyvor.dev/docs/customer-manuals/guestkit
tenant_id: public
access_level: public
updated_at: "2026-07-30"
---

# GuestKit disk inspection

## Purpose

GuestKit inspects guest disks (VMDK/qcow2) before HyperSDK conversion. It reports
guest OS family, firmware type, drivers, and blockers such as unsupported devices
or encrypted volumes.

## Typical checks

1. Mount or attach the candidate disk read-only.
2. Detect OS and bootloader configuration.
3. Inventory kernel drivers required for VirtIO.
4. Emit an inspection report ConfigMap or CR for operators to review.

## Important

GuestKit does not perform conversion by itself. Conversion remains a HyperSDK /
hyper2kvm step after operators accept the inspection report.
