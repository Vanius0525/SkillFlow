---
name: pchem-procedure
description: "Decision procedure for physical chemistry problems: how to identify which relation applies from what the problem states and asks, which sign convention governs, and how to check a result before reporting it. Use when a thermodynamics, electrochemistry, gas-law or quantum problem needs the right equation selected and applied in the right direction."
---

# Choosing and Applying the Right Relation

Method only. This skill contains no numerical constants: it tells you which
equation the problem calls for and which way the signs run, not what R is.

## When to Use

- Several relations could apply and the problem does not say which
- A sign is ambiguous (work done on versus by the system)
- A result needs checking before it is reported

## Step 1: Classify by what is given and what is asked

| Given | Asked | Relation |
| ----- | ----- | -------- |
| p, V, n, T (any three) | the fourth | perfect gas law |
| real gas, moderate p | p or V | van der Waals |
| standard cell potential | reaction free energy | free energy from cell potential |
| equilibrium constant | standard free energy | free energy from equilibrium constant |
| non-standard concentrations | cell potential | Nernst relation |
| enthalpy and entropy | free energy at a temperature | Gibbs relation |
| heat and work | internal energy change | first law |
| isothermal expansion, reversible | work | reversible isothermal work |
| particle mass and energy | wavelength | de Broglie relation |

## Step 2: Apply the sign conventions

- Work is negative when the system does work on its surroundings and positive
  when the surroundings do work on the system.
- A spontaneous process has negative standard free energy change.
- A positive standard cell potential corresponds to a negative standard free
  energy change, so the two always carry opposite signs.
- Heat absorbed by the system is positive.
- For an equilibrium constant greater than one, the standard free energy change
  is negative.

## Step 3: Handle the electron count

Reactions expressed per mole of electrons and reactions expressed per mole of
reactant differ by the number of electrons transferred. Read the half-reaction
as written and count the electrons appearing in it. A half-reaction written with
one electron has an electron count of one even when the overall cell reaction
transfers more.

## Step 4: Check before reporting

1. **Sign**: does it match what Step 2 predicts for this process?
2. **Magnitude**: free energies of reaction are typically tens to hundreds of
   kJ per mole; a result thousands of times outside that range usually means a
   factor of 1000 or an electron count was missed.
3. **Units**: the requested unit is stated in the problem. Convert at the end,
   not in the middle.
4. **Direction**: if the problem reverses a tabulated reaction, the sign of the
   free energy and of the cell potential both reverse.

## Common Failure Modes

- Using a gas constant whose units do not match the rest of the expression.
- Reporting joules where kilojoules were requested, or the reverse.
- Forgetting that a reversed half-reaction flips the sign.
- Treating a temperature in Celsius as if it were absolute.
- Applying the standard relation when the problem states non-standard
  conditions, where the Nernst relation is required instead.
