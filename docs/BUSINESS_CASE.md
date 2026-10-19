# Business case

Status: business hypothesis and proposed scope. No measured productivity benefit or production usage yet.

## Problem and stakeholders

Employees request application access through JSM. IT agents repeatedly identify the application and permission level, request missing justification, determine the reviewer, and update routing. Incomplete requests create back-and-forth; privileged requests risk reaching the wrong owner.

Employees need clear next steps. IT agents need consistent preparation and a visible failure queue. Application owners and security reviewers retain access decisions. The technical product owner validates value and scope; an operator owns credentials, configuration, and recovery.

## Current and proposed process

Today an agent reads each ticket, checks completeness, asks questions, finds the owner, routes the ticket, and checks the human decision manually.

The implemented worker automatically discovers real eligible requests, extracts application/access level/justification, validates a small configurable catalogue, classifies the work, and prepares an internal next-action summary. It persists results, retries and audit history, with authenticated local operations. One separately approved automatic internal comment was verified on AIS-5 with no duplicate across polling/restart. That approval is consumed and the running service is back in dry-run. Incomplete work identifies exactly which details IT should request; privileged or uncertain work requires human review.

This removes the repeated preparation of a triage summary from the operator's workflow. It does not remove the human steps of contacting the requester, deciding authorization, or fulfilling access. Current write-back is an internal comment; no Jira queue, assignment, status, approval, or application permission is changed. Wider routing and native approval observation require separately validated capabilities.

## Expected value and measurement

Potential value is less repetitive triage and fewer missed required details, with traceable handling and visible failures. These are hypotheses. Measure actual processing latency, correctness per scenario, repeated effects prevented, failures recovered, and manually performed preparation steps on sandbox cases. Compare observed manual/automated steps before claiming time savings. No ROI, adoption, or employee-volume figure is asserted.

## Assumptions and risks

A dedicated JSM sandbox, an authorized agent identity, a maintainable application catalog, and named reviewers are prerequisites. The account's actual workflow and plan may restrict implementation. Ambiguous language must lead to clarification or review. Credential exposure, wrong routing, repeated comments, and uncertain API outcomes require explicit boundaries, durable state, and operational ownership.

## Out of scope

Provisioning/revoking application permissions, autonomous authorization, paid account upgrades, changes to business projects, public deployment, enterprise SSO rollout, a complex frontend, and LLM-based extraction before deterministic live acceptance.
