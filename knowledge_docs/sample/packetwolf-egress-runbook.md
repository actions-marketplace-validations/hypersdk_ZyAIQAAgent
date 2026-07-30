---
title: PacketWolf egress verification runbook
product: PacketWolf
version: "2.0"
source: runbook
url: https://zyvor.dev/docs/runbooks/packetwolf-egress-verify
tenant_id: public
access_level: public
updated_at: "2026-07-30"
---

# Runbook: verify PacketWolf egress deny

## Steps

1. Apply the default-deny egress policy to the target namespace.
2. Confirm DNS egress remains allowed.
3. From a test pod, attempt an external HTTPS request and expect failure.
4. From the same pod, reach another pod in the namespace and expect success.
5. Use Hubble flows to confirm dropped external packets and allowed in-namespace
   traffic before declaring the change verified.
