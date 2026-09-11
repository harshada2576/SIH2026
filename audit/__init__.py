"""audit — tamper-evident, cryptographically-signed alert ledger ("blockchain-lite").

Deliberately NOT a real distributed/permissioned blockchain (Hyperledger
Fabric etc.) — that is a multi-week infra project, listed as target
production architecture in Must-Read/Phases.md, not something a prototype
should fake. What this package gives you for real, today:

  1. Every RiskAlert is hashed and chained to the previous alert's hash
     (classic hash-chain / Merkle-style linking).
  2. Every block is signed with an Ed25519 keypair generated once and stored
     locally — proving *which* instance produced the alert.
  3. verify() walks the whole chain and will catch (a) a tampered payload,
     (b) a deleted/reordered block, or (c) an invalid signature.

That is precisely the property judges care about ("can we trust this alert
wasn't altered after the fact and know who issued it?") without pretending to
have built a permissioned multi-node blockchain network in 3 days.
"""
