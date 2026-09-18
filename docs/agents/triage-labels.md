# Triage Labels

The skills speak in terms of five canonical triage roles. This file maps those roles to the actual label strings used in this repo's issue tracker.

This repo uses the canonical vocabulary unchanged — all five labels exist on
`erikgunawans/ent-os-new-jup` and can be applied directly.

| Label in mattpocock/skills | Label in our tracker | Meaning                                  |
| -------------------------- | -------------------- | ---------------------------------------- |
| `needs-triage`             | `needs-triage`       | Maintainer needs to evaluate this issue  |
| `needs-info`               | `needs-info`         | Waiting on reporter for more information |
| `ready-for-agent`          | `ready-for-agent`    | Fully specified, ready for an AFK agent  |
| `ready-for-human`          | `ready-for-human`    | Requires human implementation            |
| `wontfix`                  | `wontfix`            | Will not be actioned                     |

When a skill mentions a role (e.g. "apply the AFK-ready triage label"), use the corresponding label string from this table.

Edit the right-hand column to match whatever vocabulary you actually use.

## Note on inherited labels

This tree descends from `open-webui/open-webui`, but the labels above were created
fresh on `erikgunawans/ent-os-new-jup`. Upstream's own vocabulary (`core`, `non-core`,
`confirmed issue`, `testing wanted`, …) is **not** present here and carries no meaning
for triage. Don't reach for it.
