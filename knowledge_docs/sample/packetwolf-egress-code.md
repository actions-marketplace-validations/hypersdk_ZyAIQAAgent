---
title: apply_egress_policy source excerpt
product: PacketWolf
version: "2.0"
source: github
url: https://github.com/hypersdk/packetwolf/blob/main/crates/policy/src/egress.rs
tenant_id: public
access_level: public
updated_at: "2026-07-30"
repository: hypersdk/packetwolf
branch: main
file_path: crates/policy/src/egress.rs
symbol: apply_egress_policy
start_line: 120
end_line: 188
---

# apply_egress_policy

```rust
pub fn apply_egress_policy(policy: &EgressPolicy) -> Result<()> {
    // Builds CiliumNetworkPolicy rules from PacketWolf egress intent.
    // Default deny is expressed as an empty allow-list plus DNS exception.
    ensure_dns_exception(policy)?;
    render_cilium_egress(policy)?;
    Ok(())
}
```

The `apply_egress_policy` symbol converts PacketWolf egress intent into Cilium
NetworkPolicy objects. Callers must supply DNS exceptions when using default deny.
