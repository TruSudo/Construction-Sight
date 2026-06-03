# AI Augmentation, Autonomous Enrichment, and Bidding Automation Model

## Status

Accepted design direction.

## Purpose

ConstructionSight should use AI as a cross-cutting augmentation layer wherever it meaningfully improves user experience, reduces manual effort, improves comprehension, accelerates enrichment, or helps generate tailored business outputs. AI should not be limited to proposal writing. It should assist throughout source discovery, enrichment, search, summarization, opportunity analysis, and bidding workflows.

This model defines AI's role across the platform, including autonomous background enrichment, prompt-driven workflows, contract bidding support, user-facing simplicity, and anti-fabrication constraints.

## Core Rule

AI should reduce the user's work, not turn the user into an investigator.

AI may suggest, classify, summarize, rank, enrich, explain, draft, and route work. It must remain evidence-bound, user-controllable, and auditable.

## Default User Simplicity Rule

ConstructionSight is not primarily an investigator-only tool. The normal user is trying to find where construction is happening, who is involved, whether an opportunity exists, and what to do next.

The user should not be forced to approve or deny every possible fact, candidate relationship, or enrichment hypothesis during routine use.

Default behavior:

- AI enriches automatically;
- the app displays useful status labels;
- confidence and evidence are accessible on demand;
- uncertainty is not hidden, but it is not presented as a burden;
- review workflows are advanced/optional unless a user-impacting or externally visible action is involved.

## No Smoke / No Burden Rule

ConstructionSight must avoid both extremes:

- do not annoy users with internal uncertainty as if they must finish the investigation;
- do not exaggerate or present uncertain information as confirmed truth.

The product should be useful, not inflated; simple, not deceptive; confident, but evidence-bound.

Avoid primary labels such as:

- `needs more data`;
- `unknown`;
- `insufficient evidence`;
- `unresolved`.

Prefer useful, precise labels such as:

- `Active Site - GC Identified`;
- `Developer not publicly identified from current sources`;
- `Authority partially identified`;
- `Public record match found`;
- `Likely active project`;
- `Early-stage project`;
- `Relationship under enrichment`;
- `Security-relevant context available`.

## AI Modes

ConstructionSight should support two AI modes:

1. **User-prompted AI**: the user asks for something directly.
2. **Autonomous AI enrichment**: the system proactively improves records, relationships, summaries, and opportunities without user prompting.

## User-Prompted AI

Users should be able to use plain language prompts such as:

- show me active security opportunities in Fontana with known GCs;
- find projects entering vertical construction where the developer is not identified;
- explain why this project is marked as a candidate opportunity;
- generate a security pitch for this GC using my saved brochure;
- summarize this developer's active sites;
- prepare a follow-up email for this bid.

AI should translate those prompts into searches, filters, enrichment jobs, summaries, or draft outputs.

## Autonomous AI Enrichment

Autonomous enrichment may run after source refresh, record discovery, user search, or project update.

It may assist with:

- source classification;
- field interpretation;
- permit description classification;
- boolean scope tags;
- project-cluster candidate generation;
- phase summary;
- opportunity ranking;
- authority-enrichment suggestions;
- entity disambiguation suggestions;
- coverage-gap recommendations;
- source failure explanation;
- plain-language project summaries;
- relationship explanations;
- bid readiness suggestions.

## AI Autonomy Levels

Suggested levels:

- `level_0_none`: deterministic processing only;
- `level_1_explain`: AI summarizes or explains existing evidence;
- `level_2_suggest`: AI proposes tags, relationships, clusters, searches, or enrichment targets;
- `level_3_prepare`: AI drafts outputs or queues low-risk enrichment jobs;
- `level_4_auto_apply_low_risk`: AI may auto-apply low-risk classifications under defined confidence and evidence rules;
- `requires_review`: high-impact actions require user or admin approval.

## Low-Risk AI Auto-Apply Candidates

AI may auto-apply or quietly store low-risk enrichment when confidence is sufficient:

- plain-language summaries;
- scope tag suggestions with evidence;
- search query expansion;
- source failure explanations;
- opportunity ranking hints;
- coverage-gap recommendations;
- low-risk categorization;
- user-facing simplification of technical statuses.

These should still preserve AI provenance.

## Review Required Actions

Review or explicit user approval should be required for:

- externally sending proposals or emails;
- finalizing bid packages;
- changing user-owned marketing material;
- promoting an out-of-zone jurisdiction to active monitoring;
- using crime-context language in advertising material;
- high-impact entity merges;
- developer/director authority conclusions where evidence is weak or conflicting;
- changing billing/royalty settings;
- deleting or overwriting user material.

## AI Provenance

AI-generated or AI-assisted outputs should preserve:

- AI-generated flag;
- model/provider where available;
- prompt/template version;
- input evidence references;
- user material references;
- created timestamp;
- confidence where applicable;
- accepted/edited/rejected status;
- final user-approved version where applicable.

## Business Material Library

Users should be able to upload and save:

- brochures;
- capability statements;
- marketing copy;
- service descriptions;
- pricing summaries;
- past project summaries;
- insurance/license/bonding documents;
- certifications;
- photos;
- standard proposal language;
- email templates;
- bid response templates.

These materials form the user's private business profile library.

## AI Proposal and Bidding Automation

When a user selects an opportunity, project, GC, developer, or contact, AI may generate tailored material using:

- user-approved business materials;
- ConstructionSight project evidence;
- entity profile details;
- opportunity category;
- lifecycle phase;
- prior outreach history;
- optional crime context if enabled and appropriate;
- user instructions.

Generated outputs may include:

- outreach email;
- bid/proposal draft;
- capability statement;
- talking points;
- follow-up message;
- executive summary;
- site-specific value proposition;
- marketing one-sheet.

## Anti-Fabrication Constraints

AI must not:

- invent company capabilities;
- invent certifications;
- invent insurance/bonding status;
- invent pricing;
- invent client history;
- invent project facts;
- invent crime/risk claims;
- present inference as verified fact;
- send external material without user approval;
- use uploaded marketing material as public-record evidence.

## User Material vs Public Evidence

ConstructionSight must distinguish:

- user-uploaded business material;
- public project/source evidence;
- AI-generated customization;
- final user-approved output.

A proposal may combine them, but the system should not confuse them.

## Prompt-First Simplicity

The user should be able to ask for outcomes rather than operate complex workflows.

Examples:

- make me a security pitch for this project;
- show me the best leads to call today;
- summarize why this GC matters;
- write a follow-up email using my brochure;
- explain this opportunity in plain English.

The system should route the request to the correct data, template, enrichment, or generation workflow.

## Non-Negotiable Constraints

- AI should reduce user burden.
- AI should not hide uncertainty.
- AI should not inflate weak evidence.
- AI should not fabricate.
- AI should not force ordinary users into investigative approval loops.
- AI should not take externally visible actions without approval.
- AI should preserve evidence and provenance.
- AI should not replace deterministic rules where deterministic rules are safer.

## Product Meaning

The AI augmentation model makes ConstructionSight feel intelligent and simple. It turns complex public construction data into clear answers, useful summaries, tailored bidding material, and automatic enrichment while preserving truthfulness, evidence, and user control.
