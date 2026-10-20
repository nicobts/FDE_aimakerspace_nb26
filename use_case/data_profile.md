# Data profile: <your use case>

<!--
  Template from 00_Prerequisites/6_Your_Data. Fill it in with the team that owns the data.
  One page, shape only: nothing in it that is a row, no real hostnames, names or identifiers.
  This repo is public. Describe the system ("the ticketing system"), do not name internal URLs.
  Fill in the last section first: it decides which strategy you are allowed to use.
-->

**Source system and owner:** <system> / <team, role>
**Classification and scope:** <public | internal | confidential>; who may see it; anything under hold
**Arrives as:** <JSONL | CSV | Parquet | API response | PDF | image | audio>, <rows per day>

## Schema
| Field | Type | Required | Notes (free text? identifier pattern? enum values?) |
| --- | --- | --- | --- |

## Identifier patterns
<field>: <regex or example shape with digits replaced by 9s>

## What varies (the axes)
- Who produces it: ...
- How long / how messy: ...
- The rare categories, and roughly how rare: ...
- The case the system should decline: ...

## What "correct" looks like, and who judges it
<role>, in <system>; where the already-judged ones live

## Five golden examples
Written from memory, every name and id invented -> use_case/evals/golden.jsonl

## Non-text content
Scans / screenshots / recordings? Which of Session 6's four questions apply?

## What I am NOT allowed to do with this data
<export | send to external model | share pseudonymized | share numbers only>
