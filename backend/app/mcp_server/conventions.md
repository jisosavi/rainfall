# Nordic weather observations: data conventions

Daily weather observations from national weather services, processed into common daily values.

## Coverage
- Finland (FMI), Norway incl. Svalbard and Jan Mayen (MET Norway), Sweden (SMHI), Denmark,
  Greenland and the Faroe Islands (DMI), Iceland (IMO), Estonia (Keskkonnaagentuur).
- About 2,800 stations; daily data from 1 January 2025. Updated twice a day (07:15 and 13:15 UTC).

## Measurements and the day they cover
| Measurement | Unit | Day D means |
|---|---|---|
| precipitation | mm | total from 06 UTC on D to 06 UTC on D+1 (Iceland: 09 UTC on D to 09 UTC on D+1) |
| snow_depth | cm | reading on the morning of D (06 UTC; Iceland 09 UTC); 0 = no snow |
| temp_mean | °C | mean over 00–24 UTC on D |
| temp_min | °C | lowest from 18 UTC on D-1 to 18 UTC on D |
| temp_max | °C | highest from 18 UTC on D-1 to 18 UTC on D |

Consequences:
- Yesterday's rainfall exists only after 06 UTC today. Estonia's rainfall arrives a day later,
  Iceland's 3–4 days later.
- Rain that falls before 06 UTC counts for the previous date.

## Missing vs zero
- A value of 0 is a real observation (no rain, no snow).
- `has_data: false` means the station operated but has no valid value that day (missing).
- Where a provider's daily value covers another period, ours is computed from hourly values;
  a day with too few hours is missing (rain 23 of 24, mean temperature 20, min/max 22).

## Quality flags
- `suspect_spatial`: far from all nearby stations that day (rain and snow: far above them;
  temperature: far warmer or colder). Shown as reported, but left out of rankings and summaries.
- `confirmed_hourly`: unusually high rainfall confirmed by the station's own hourly readings;
  counts as normal.
- Impossible values (over 300 mm rain, 600 cm snow, outside −60 to +40 °C) are stored as missing.

## Licence and attribution
All data is CC BY 4.0 (MET Norway also NLOD 2.0). When publishing results, credit the providers:
"Data: FMI, MET Norway, SMHI, DMI, IMO and Keskkonnaagentuur (CC BY 4.0), processed by Nordic
weather observations (https://isosavi.com/test/rainfall/)."
