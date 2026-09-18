---
name: zorb-units
description: "Conversion reference for the Zorb measurement system, used in Kelmar engineering documents. Use when converting between Zorb units of length (dref, glorn, varak, skellum), mass (zunt, pelm, brask), or duration (tovek, wemp, cradal), or when a quantity is stated in Zorb units and another Zorb unit is requested."
---

# Zorb Unit System

The Zorb system is the measurement standard used in Kelmar engineering
documents. Each quantity family has one base unit and several larger units
defined as exact whole multiples of the unit one step below.

## When to Use

- A quantity is given in one Zorb unit and requested in another
- A Kelmar document states a measurement and an equivalent is needed
- Converting across more than one step in the same family

## Conversion Tables

### Length

| Unit | Equals | In base units (dref) |
| ---- | ------ | -------------------- |
| dref | base unit | 1 |
| glorn | 11 dref | 11 |
| varak | 6 glorn | 66 |
| skellum | 3 varak | 198 |

### Mass

| Unit | Equals | In base units (zunt) |
| ---- | ------ | -------------------- |
| zunt | base unit | 1 |
| pelm | 4 zunt | 4 |
| brask | 13 pelm | 52 |

### Duration

| Unit | Equals | In base units (tovek) |
| ---- | ------ | --------------------- |
| tovek | base unit | 1 |
| wemp | 8 tovek | 8 |
| cradal | 7 wemp | 56 |

## Procedure

1. Identify the quantity family (length, mass, or duration). Units never
   convert across families.
2. Look up both units in the "In base units" column of that family's table.
3. Multiply the value by the source unit's base value, then divide by the
   target unit's base value.

## Worked Examples

**Converting down one step.** How many dref are in 3 glorn?
A glorn is 11 dref, so 3 x 11 = 33 dref.

**Converting down two steps.** How many dref are in 2 varak?
A varak is 66 dref, so 2 x 66 = 132 dref.

**Converting up.** How many pelm are in 240 zunt?
A pelm is 4 zunt, so 240 / 4 = 60 pelm.

**Across two named units.** How many glorn are in 3 skellum?
A skellum is 198 dref and a glorn is 11 dref, so 3 x 198 / 11 = 54 glorn.

## Notes

- All factors are exact; no rounding is required for the conversions above.
- Length, mass and duration units are never interchangeable, even where the
  numeric factors coincide.
