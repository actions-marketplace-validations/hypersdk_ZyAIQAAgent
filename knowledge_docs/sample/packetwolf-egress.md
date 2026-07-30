---
title: PacketWolf Egress Controls
product: PacketWolf
version: "2.0"
source: customer-manual
url: https://zyvor.dev/docs/customer-manuals/packetwolf
tenant_id: public
access_level: public
updated_at: "2026-07-30"
---

# PacketWolf Egress Controls

## Deny external internet access

PacketWolf can enforce an egress-deny policy for a selected pod, virtual machine
workload or namespace. Start with a default-deny egress policy and then add explicit
destinations that the workload is allowed to reach.

Before enforcement, verify DNS, cluster service CIDRs and required control-plane
destinations. Blocking all egress without these exceptions can prevent name resolution
and required service communication.

## Allow namespace-only traffic

To allow communication within one namespace while denying destinations outside the
cluster, match the destination namespace labels and the cluster pod CIDRs. Keep DNS
access explicitly permitted. Verify the result with Cilium or Hubble flow observations
before applying the policy broadly.

A recommended rollout is:

1. Observe current flows.
2. Generate the candidate policy.
3. Apply it to one test workload.
4. Verify permitted namespace traffic.
5. Verify that external traffic is denied.
6. Expand the policy after validation.

## ICMP and port controls

ICMP can be denied independently from TCP or UDP. Port-specific controls should identify
the protocol as well as the port. For example, TCP port 80 and UDP port 80 are different
policy entries.
