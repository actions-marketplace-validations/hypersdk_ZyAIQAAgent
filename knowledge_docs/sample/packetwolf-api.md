---
title: PacketWolf NetworkPolicy API
product: PacketWolf
version: "2.0"
source: api-reference
url: https://zyvor.dev/docs/api/packetwolf/networkpolicy
tenant_id: public
access_level: public
updated_at: "2026-07-30"
---

# PacketWolf NetworkPolicy API

## Create policy

`POST /apis/networking.packetwolf.io/v1alpha1/namespaces/{namespace}/networkpolicies`

Creates a PacketWolf NetworkPolicy. The request body must include `spec.egress`
with either a default-deny rule or explicit allow destinations. DNS egress should
be listed explicitly when default-deny is enabled.

## Get policy

`GET /apis/networking.packetwolf.io/v1alpha1/namespaces/{namespace}/networkpolicies/{name}`

Returns the current PacketWolf NetworkPolicy including status conditions that
report whether Hubble has observed matching flows.
