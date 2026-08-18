---
name: pchem-constants
description: "Reference values for physical chemistry calculations: gas constant in every common unit system, Faraday constant, Avogadro, Planck, Boltzmann, electron mass and charge, plus the unit conversions these problems need (atm to Pa, L atm to J, eV to J, Celsius to Kelvin). Use whenever a thermodynamics, kinetics, electrochemistry or quantum chemistry problem requires a numerical constant or a unit conversion."
---

# Physical Chemistry Constants and Conversions

Numerical reference only. This skill contains values, not methods: it tells you
what R is in the units you need, not which equation to put it in.

## When to Use

- A calculation needs a fundamental constant
- A quantity must be converted before it can enter an equation
- A result is in the wrong unit for the requested answer

## Fundamental Constants

| Symbol | Name | Value |
| ------ | ---- | ----- |
| R | gas constant | 8.314 J K^-1 mol^-1 |
| R | gas constant | 0.08206 L atm K^-1 mol^-1 |
| R | gas constant | 8.314 x 10^-2 L bar K^-1 mol^-1 |
| R | gas constant | 82.06 cm^3 atm K^-1 mol^-1 |
| F | Faraday constant | 96485 C mol^-1 |
| N_A | Avogadro constant | 6.022 x 10^23 mol^-1 |
| k_B | Boltzmann constant | 1.381 x 10^-23 J K^-1 |
| h | Planck constant | 6.626 x 10^-34 J s |
| hbar | reduced Planck constant | 1.055 x 10^-34 J s |
| c | speed of light | 2.998 x 10^8 m s^-1 |
| m_e | electron rest mass | 9.109 x 10^-31 kg |
| e | elementary charge | 1.602 x 10^-19 C |
| g | standard gravity | 9.807 m s^-2 |

## Unit Conversions

| From | To | Multiply by |
| ---- | -- | ----------- |
| atm | Pa | 101325 |
| atm | bar | 1.01325 |
| bar | Pa | 100000 |
| torr | atm | 1/760 |
| L atm | J | 101.325 |
| eV | J | 1.602 x 10^-19 |
| cal | J | 4.184 |
| dm^3 | L | 1 (identical) |
| dm^3 | m^3 | 10^-3 |
| angstrom | m | 10^-10 |
| nm | m | 10^-9 |

## Temperature

- T/K = theta/degC + 273.15
- Standard ambient temperature 25 degC = 298.15 K
- Ice point 0 degC = 273.15 K

## Standard States

- Modern convention: p-standard = 1 bar = 10^5 Pa
- Older texts (and many textbook problems): p-standard = 1 atm = 101325 Pa
- Standard concentration: 1 mol dm^-3

## Notes

- Match R to the units already present in the problem. Pressure in atm with
  volume in dm^3 pairs with R = 0.08206; energy in joules pairs with R = 8.314.
- Answers in kJ mol^-1 require dividing a joule result by 1000.
