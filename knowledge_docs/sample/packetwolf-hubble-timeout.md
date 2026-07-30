---
title: PacketWolf Hubble Relay timeout
product: PacketWolf
version: "2.0"
source: known-issue
url: https://zyvor.dev/docs/known-issues/hubble-relay-timeout
tenant_id: public
access_level: public
updated_at: "2026-07-30"
---

# Known issue: Hubble Relay timeout after 15000ms

## Symptoms

Operators may see `Hubble Relay timeout after 15000ms` when PacketWolf policy
verification cannot reach the Hubble Relay service on port 4245.

## Likely causes

- NetworkPolicy or CiliumNetworkPolicy denying hubble-relay in `kube-system`
- Hubble Relay pods not ready
- Incorrect cluster DNS for `hubble-relay.kube-system.svc`

## Mitigation

1. Confirm `cilium status --wait` reports Hubble as healthy.
2. Allow egress from the verifying workload to hubble-relay:4245.
3. Retry PacketWolf verification after the relay is reachable.
