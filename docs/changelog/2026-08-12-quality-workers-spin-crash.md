# 2026-08-12 — Quality workers: tier cap + confirm (not hard lock to 1)

## Summary

Quality / Best Quality no longer hard-lock Workers to 1. Parallel workers are
allowed up to a GPU-tier cap, with a confirmation dialog before going above 1.
The earlier crash from spinbox rebind/clamp feedback remains fixed.

## Caps

| GPU tier | Quality / Best Quality max workers |
|----------|-------------------------------------|
| low (e.g. 1050 Ti / &lt;6GB) | 1 |
| mid | 3 |
| high (e.g. 3060+) | 5 |

Balance / Fast / Very Fast keep the previous rules (up to 10; QHD/4K max 2).

## UX

Raising Workers above 1 on Quality / Best Quality shows:

> Are you sure your PC can run N workers at the same time…?

No → stay on the previous value. Yes → apply and save.

## Surfaces

- `camxora_python` desktop only.
