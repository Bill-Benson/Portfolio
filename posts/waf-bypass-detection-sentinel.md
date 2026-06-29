---
title: Catching the Attacks a WAF Misses with Microsoft Sentinel
date: 2026-06-29
description: A detection-engineering lab that ingests ModSecurity and NGINX logs into Microsoft Sentinel and uses a single leftanti KQL join to surface attacks that slipped past the WAF. It rediscovered a boolean-blind SQLi bypass from my dissertation that returns HTTP 200 with no rule hit at both Paranoia Level 1 and 2.
tags: Detection Engineering, Microsoft Sentinel, KQL, WAF
---

This post walks through a SIEM project I built on top of my MSc dissertation data. The dissertation measured how well ModSecurity caught attacks; this project asks the opposite, operational question: when an attack *does* get through, can I detect it after the fact from logs alone? Code and queries are on [GitHub](https://github.com/Bill-Benson/sentinel-waf-detection).

## The Problem

A Web Application Firewall is not perfect, and everyone who runs one knows it. Some attacks match no rule and sail through to the application. The dangerous part isn't that a bypass exists — it's that, from the WAF's point of view, nothing happened. There's no alert, no blocked-request log, no rule ID. The attack is invisible precisely because the control that was supposed to see it didn't.

So the WAF's own logs can't tell you about a bypass. By definition, a bypass leaves no trace there. You need a second source of truth — what the *server* actually did — and a way to compare the two.

## The Core Idea

I ingest two different logs into Microsoft Sentinel and treat them as two opinions about the same traffic:

- **ModSecurity audit logs** → the `WAFAudit_CL` table. This is *what the WAF caught*: matched rule IDs (942xxx for SQLi, 941xxx for XSS), rule messages, attack categories, paranoia level.
- **NGINX access logs** → the `WAFAccess_CL` table. This is *what actually happened*: every request, its HTTP status, URI, bytes, user-agent, paranoia level.

A bypass is the gap between them: a request that **looks like an attack** and **succeeded** (HTTP 200), but which **never appears in the WAF's list of things it caught**. Find that gap and you've found what the firewall missed.

## Getting the Logs In

Sentinel sits on Log Analytics, and the modern way to push custom logs into it is the **Azure Monitor Logs Ingestion API**. The path looks like this:

1. A **Data Collection Endpoint (DCE)** gives me an HTTPS endpoint to post to.
2. A **Data Collection Rule (DCR)** defines the schema for each custom table and routes incoming records to it.
3. A small **Python parser** reads the raw ModSecurity and NGINX logs, shapes them into the table schema, and posts them to the DCE.

The piece I want to call out is the identity. Instead of using a broad credential, I created a **Microsoft Entra app registration** and granted it only the **Monitoring Metrics Publisher** role, scoped to the DCR itself — not the subscription, not the resource group. The app can write telemetry to exactly one place and can do nothing else. That least-privilege scoping is the difference between "a leaked credential writes some logs" and "a leaked credential owns the subscription," and it costs nothing to do correctly from the start.

The lab dataset came to roughly 5,000 events — about 2,520 audit verdicts and 2,492 access events — spanning Paranoia Level 1 and Level 2 test runs from the dissertation.

## The Detection: One `leftanti` Join

The headline query is short, which is the point. Good detection logic should be legible. It works in three steps:

**1. Find attack-shaped requests that succeeded.** Filter `WAFAccess_CL` for `HTTP 200` responses whose URI matches the *grammar* of an attack — structural signatures like `(SELECT`, `CASE WHEN`, `<script`, or `onerror` in their percent-encoded forms. Matching structure rather than bare keywords keeps the noise down: I want requests that are shaped like SQLi or XSS, not every request that happens to contain the word "select".

**2. Subtract everything the WAF caught.** Run a `leftanti` join against `WAFAudit_CL` rows where `isnotempty(RuleId)`. The `leftanti` operator is the key — it returns rows from the left table that have *no* match on the right. So "attack-shaped successful requests" minus "requests the WAF flagged" leaves exactly the requests that got through unseen.

**3. What's left is the bypass set**, made distinct by URI and `ParanoiaLevel`.

That `leftanti` join is doing the conceptual heavy lifting: it's set subtraction between "what happened" and "what the WAF noticed." Everything in the result is, by construction, something the firewall missed.

## What It Found

The query surfaced a boolean-blind SQLi payload:

```
1 AND (SELECT CASE WHEN (1=1) THEN 1 ELSE 0 END)=1
```

This is dissertation case **SQLI_33**. It returned HTTP 200 with **no matching rule at both Paranoia Level 1 and Level 2** — which is the interesting detail. A bypass that closes when you raise the paranoia level is a threshold problem; you were one notch too lenient. A bypass that survives *both* levels means the signature simply isn't there. No amount of turning the existing dials would have caught it. That lines up with the dissertation's broader finding that raising the paranoia level mostly reshuffles threshold arithmetic rather than adding genuinely new detection coverage.

The validation loop is what makes this satisfying: because I already knew from the dissertation that SQLI_33 was a real bypass, rediscovering it *purely from logs* — with no prior knowledge baked into the query — is evidence that the detection method works on ground truth, not just in theory.

## Why I Built It This Way

The whole project is an argument for defence in depth. A WAF is a control, not a guarantee, and the right response to "controls fail" isn't a better WAF — it's a second layer that assumes the first one leaked. Comparing the firewall's verdict against the server's actual behaviour is a general pattern: any time you have a control that's supposed to block something, logging *both the control's decision and the real outcome* lets you detect the cases where the two disagree.

It also kept me honest about cloud hygiene. Scoped RBAC, a dedicated app registration, and a custom schema instead of dumping everything into one table — none of that is glamorous, but it's the difference between a demo and something you'd be comfortable running against real traffic.

The full KQL and the ingestion tooling are on [GitHub](https://github.com/Bill-Benson/sentinel-waf-detection).
