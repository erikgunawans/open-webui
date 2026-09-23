# Skills ported from holaOS

These skills were copied on 2026-09-23 from holaOS by Holaboss (`~/holaboss-ai` at commit `a6b58be`), at Erik's request. The copy was read-only on that side: nothing was written, built or installed in holaboss-ai.

## Licence

- **holaOS is licensed under a modified Apache License 2.0.** The full text is in [`LICENSE-holaOS`](LICENSE-holaOS).
  - Its extra condition 1a restricts offering holaOS "in whole or substantial part" as a hosted service or commercial component for third parties.
  - A set of prompt-text skill files is not holaOS in substantial part.
  - BangJayaOS is used inside JUP, and the licence states that internal use within a single organisation needs no commercial licence.
  - **If BangJayaOS is ever offered to parties outside JUP, re-check this with Holaboss before shipping these skills.**
- **stop-slop** is © 2025 Hardik Pandya under MIT. Its licence is kept in [`stop-slop/LICENSE`](stop-slop/LICENSE).
- In line with Apache-2.0 §4, each skill's content in the app carries an attribution footer naming its origin and licence.

## What changed

The skill text is unmodified, with two mechanical exceptions, both made by `deploy/gcp/sync-skills.ts` at load time:

1. The YAML frontmatter is read into the skill's name, description and tags. The display name is the skill's own `# Heading`.
2. `stop-slop`'s three `references/*.md` files are inlined after its body, because an app skill is a single text field. Its "See [references/x.md](…)" links become "See Reference: x.md below."

## What was taken, and what was left out

**Taken (16), all prompt-only with no holaOS tool references:**
- audience-analyst
- content-planner
- content-writer
- data-analyst
- email-writer
- idea-generator
- meeting-notes
- performance-reporter
- prd-writer
- proposal-writer
- summarizer
- tone-adapter
- translator
- repurpose-content
- linkedin-post
- stop-slop

**Left out (16):**

| Skill(s) | Why it was left out |
|---|---|
| web-researcher, trend-spotter, competitor-analysis | They instruct the model to research the web. Web search is off on this deployment, so the model would invent sources, which breaks contract rule 1. Revisit after the web-search egress decision. |
| image-generator, video-generator | Image generation is off: its provider call bypasses the governance funnel (ADR-0002 amendment). There is no video generation at all. |
| app-builder-sdk, build-dashboard, browser-core-efficient, browser-qa, capability-creator, customize-capability, mcp-configurator, skill-creator, skill-installer | These drive holaOS's own runtime, SDK and tools, which do not exist here. |
| frontend-design, interface-design | These are coding-agent design skills, not a chat use case. interface-design also carries its own separate licence. |

## Governance

A ported skill is text appended to a governed turn. The JUP operating contract still binds every answer, so these skills cannot license an invented figure. They are generic (marketing, writing, analysis) and know nothing about JUP. When a JUP question needs figures, the JUP tier-discipline skill and the knowledge base govern the answer, not these skills.
