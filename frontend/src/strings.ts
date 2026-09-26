import type { Parameter } from './api'

// All user-facing text (UK English), kept in one place so it can be translated later.
export const t = {
  title: 'Nordic weather observations',
  subtitle: 'Daily rainfall, snow depth and temperature at Nordic weather stations',
  loading: 'Loading…',
  loadError: 'Could not load the data. Please try again later.',
  noDataYet: 'No data available yet.',
  noStationsForDate: 'No stations reported on this date.',
  previousDay: 'Previous day',
  nextDay: 'Next day',
  latest: 'Latest',
  chooseDate: 'Date',
  viewLabel: 'View',
  viewMap: 'Map',
  viewList: 'List',
  viewTop: 'Top 15',
  topHeading: {
    precipitation: 'Top 15 rainfall',
    snow_depth: 'Top 15 snow depth',
    temp_mean: 'Top 15 mean temperature',
    temp_min: 'Top 15 minimum temperature',
    temp_max: 'Top 15 maximum temperature',
  },
  periodLabel: 'Period',
  periods: {
    week: 'Week',
    month: 'Month',
    year: 'Year',
    last30: 'Last 30 days',
    now: 'Now',
    winter_max: 'Deepest this winter',
    winter_days: 'Snow days this winter',
  },
  periodRange: (start: string, end: string) => `${start} – ${end}`,
  allStations: 'Include stations with gaps',
  allStationsHint: 'By default only stations with data on at least 90% of the days are ranked.',
  coverage: (n: number, total: number) => `${n}/${total} days`,
  snowDaysUnit: 'days',
  noRankings: {
    precipitation: 'No rain in this period, so nothing to rank.',
    snow_depth: 'No snow in this period, so nothing to rank.',
    temp_mean: 'No temperatures in this period.',
    temp_min: 'No temperatures in this period.',
    temp_max: 'No temperatures in this period.',
  },
  rankingNote: 'Values far above all nearby stations (⚠) are left out.',
  listHeading: {
    precipitation: 'Stations by rainfall',
    snow_depth: 'Stations by snow depth',
    temp_mean: 'Stations by mean temperature',
    temp_min: 'Stations by minimum temperature',
    temp_max: 'Stations by maximum temperature',
  },
  measurement: 'Measurement',
  parameterLabel: {
    precipitation: 'Rainfall',
    snow_depth: 'Snow depth',
    temp_mean: 'Mean temperature',
    temp_min: 'Minimum temperature',
    temp_max: 'Maximum temperature',
  },
  measurementLabel: { precipitation: 'Rainfall', snow_depth: 'Snow depth', temperature: 'Temperature' },
  temperatureKind: 'Temperature',
  temperatureShort: { temp_mean: 'Mean', temp_min: 'Min', temp_max: 'Max' },
  listValueHeading: { precipitation: 'Rainfall', snow_depth: 'Snow depth', temp_mean: 'Mean', temp_min: 'Min', temp_max: 'Max' },
  orderLabel: 'Order',
  orders: { warmest: 'Warmest', coldest: 'Coldest' },
  tempPeriods: { now: 'Day', week: 'Week', month: 'Month', year: 'Year', last30: 'Last 30 days' },
  // Top 15 headings for temperature, by measurement and order.
  topTempHeading: {
    temp_mean: { warmest: 'Warmest mean temperature', coldest: 'Coldest mean temperature' },
    temp_min: { warmest: 'Highest minimum (mildest nights)', coldest: 'Lowest minimum (coldest nights)' },
    temp_max: { warmest: 'Highest maximum (hottest days)', coldest: 'Lowest maximum (coldest days)' },
  },
  tempRankingNote: 'Values far warmer or colder than nearby stations (⚠) are left out.',
  onDate: (when: string) => `on ${when}`,
  elevation: 'Elevation',
  elevationValue: (m: number) => `${Math.round(m)} m`,
  station: 'Station',
  rainfall: 'Rainfall',
  snowDepth: 'Snow depth',
  noData: 'No data',
  suspectShort: 'Unusually high',
  suspectLong: 'Unusually high compared with nearby stations that day. Shown as reported, but left out of rankings.',
  suspectLegend: 'Unusually high vs nearby',
  suspectTempShort: 'Unusual for the area',
  suspectTempLong: 'Much warmer or colder than nearby stations at a similar altitude that day. Shown as reported, but may be a measuring error.',
  suspectTempLegend: 'Unusual vs nearby',
  noDataOnDate: 'No data on this date.',
  lastData: (when: string, value: string) => `Last data: ${when}, ${value}`,
  showThatDay: 'Show that day',
  neverData: 'No data from this station yet.',
  confirmedLong: 'Unusually high for the area, but confirmed by the station’s own hourly readings.',
  close: 'Close',
  region: 'Municipality',
  owner: 'Station owner',
  stationId: 'Station ID',
  coordinates: 'Coordinates',
  last30Days: 'Last 30 days',
  winterSeason: (startYear: number) => `Winter ${startYear}–${String((startYear + 1) % 100).padStart(2, '0')}`,
  seasonMax: 'Deepest this winter',
  snowCoverDays: 'Days with snow cover',
  noSnowData: 'No snow depth data from this station.',
  total: 'Total',
  warmest: 'Highest max',
  coldest: 'Lowest min',
  averageMean: 'Average mean',
  chartMean: 'Mean',
  chartRange: 'Min–max',
  noTemperatureData: 'No temperature data from this station.',
  temperatureDay: (mean: string, min: string, max: string) => `mean ${mean} · ${min} to ${max}`,
  wetDays: 'Days with rain',
  measurementNote:
    'Rainfall: the total from 06:00 UTC on that date to 06:00 UTC the next day (Iceland: 09:00–09:00 UTC; Estonia arrives a day later). Snow depth: measured on the morning of that date. Temperature: the mean over 00:00–24:00 UTC; minimum and maximum from 18:00 UTC the day before to 18:00 UTC on that date.',
  legendTitle: {
    precipitation: 'Rainfall per day',
    snow_depth: 'Snow depth',
    temp_mean: 'Mean temperature',
    temp_min: 'Minimum temperature',
    temp_max: 'Maximum temperature',
  },
  stationsWithData: (withData: number, total: number) => `${withData} of ${total} stations reporting`,
  attribution: 'Data: FMI, MET Norway, SMHI, DMI, IMO and Keskkonnaagentuur (CC BY 4.0), processed',
  aboutButton: 'About This App',
  aboutTitle: 'About This App',
  aboutBody:
    'Nordic weather observations shows the daily rainfall, snow depth and temperature measured at weather stations in Finland, Norway, Sweden, Denmark, Greenland, the Faroe Islands, Iceland and Estonia on a map. Pick a date and a measurement, and select a station for its recent history.',
  aboutDataHeading: 'Data',
  aboutDataIntro: 'Observations come from the national weather services as open data:',
  aboutDataColumns: { country: 'Country', provider: 'Data provider', stations: 'Stations', licence: 'Licence' },
  aboutStationsNote: 'Stations: number on the date and measurement shown on the map.',
  aboutProcessingNote:
    'The data has been processed: values are quality-filtered, aligned to the same daily periods (rainfall 06:00–06:00 UTC; temperature mean 00:00–24:00 UTC, minimum and maximum 18:00–18:00 UTC), and days without a value are marked as missing. Where a provider’s daily values use other periods, ours are computed from its hourly values. Impossible values are dropped; values far above all nearby stations (rain, snow), or far warmer or colder than them (temperature), are marked.',
  aboutUpdatesHeading: 'Updates',
  aboutUpdatesIntro: (utcTimes: string, localTimes: string) =>
    `Data is fetched twice a day, at ${utcTimes} UTC (${localTimes} your time). Each daily value covers 06:00–06:00 UTC, so yesterday's value can first appear in the morning run.`,
  aboutUpdatesColumns: { country: 'Country', newValues: 'New values', corrections: 'Late values and corrections', lastFetched: 'Last fetched' },
  dataUpdated: (when: string) => `Data updated ${when}`,
  dataUpdatedHint: 'When the data was last fetched. Details in About This App.',
  aboutProjectHeading: 'Project',
  aboutDeveloperPrefix: 'Developed by',
  developerName: 'Janne Isosävi',
  developerUrl: 'https://github.com/jisosavi',
  aboutFeedbackPrefix: 'Found a problem or have an idea?',
  aboutFeedbackLink: 'Send feedback on GitHub',
  aboutSourceLink: 'Source code',
  aboutCodeLicencePrefix: 'The source code is licensed under the',
  aboutCodeLicenceLink: 'GNU General Public License v3.0 or later',
  aboutCodeLicenceSuffix: '. The data licences are listed above.',
  codeLicenceUrl: 'https://github.com/jisosavi/rainfall/blob/main/LICENSE',
  feedbackUrl: 'https://github.com/jisosavi/rainfall/issues/new/choose',
  sourceUrl: 'https://github.com/jisosavi/rainfall',
  dataSources: [
    {
      source: 'fmi',
      country: 'Finland',
      provider: 'Finnish Meteorological Institute (FMI)',
      url: 'https://en.ilmatieteenlaitos.fi/open-data',
      licence: 'CC BY 4.0',
      licenceUrl: 'https://creativecommons.org/licenses/by/4.0/',
      newValues: 'Yesterday, in the morning run',
      corrections: 'The last 10 days are re-checked on every run, so revised values are picked up.',
    },
    {
      source: 'met',
      country: 'Norway',
      provider: 'Norwegian Meteorological Institute (MET Norway)',
      url: 'https://frost.met.no',
      licence: 'CC BY 4.0, NLOD 2.0',
      licenceUrl: 'https://www.met.no/en/free-meteorological-data/Licensing-and-crediting',
      newValues: 'Yesterday, in the morning run',
      corrections: 'The last 10 days are re-checked on every run. Some manual stations report a day or two late.',
    },
    {
      source: 'smhi',
      country: 'Sweden',
      provider: 'Swedish Meteorological and Hydrological Institute (SMHI)',
      url: 'https://opendata.smhi.se/',
      licence: 'CC BY 4.0',
      licenceUrl: 'https://www.smhi.se/data/om-smhis-data/villkor-for-anvandning',
      newValues: 'Yesterday, in the morning run (preliminary)',
      corrections:
        'The last 10 days are re-checked on every run; many manual stations report late. On the 3rd of each month, the last four months are replaced with SMHI’s quality-controlled values.',
    },
    {
      source: 'dmi',
      country: 'Denmark, Greenland, Faroe Islands',
      provider: 'Danish Meteorological Institute (DMI)',
      url: 'https://www.dmi.dk/frie-data',
      licence: 'CC BY 4.0',
      licenceUrl: 'https://www.dmi.dk/friedata/dokumentation/terms-of-use',
      newValues: 'Yesterday, in the morning run (rainfall and temperature computed from hourly values)',
      corrections:
        'The last 10 days are re-checked on every run. A day counts when at least 23 of its 24 hourly values are in; snow depth (Denmark) comes from mostly manual stations.',
    },
    {
      source: 'imo',
      country: 'Iceland',
      provider: 'Icelandic Meteorological Office (Veðurstofa Íslands)',
      url: 'https://api.vedur.is/weather/',
      licence: 'CC BY 4.0',
      licenceUrl: 'https://athuganir.vedur.is/disclaimer?lng=en',
      newValues: 'Snow depth and temperature: yesterday. Rainfall: after 3–4 days (quality-checked first)',
      corrections:
        'The last 10 days are re-checked on every run. Rainfall covers 09:00–09:00 UTC (3 hours later than the other countries), as no hourly data is published; snow depth is read at 09:00 UTC at manual stations.',
    },
    {
      source: 'kaa',
      country: 'Estonia',
      provider: 'Estonian Environment Agency (Keskkonnaagentuur)',
      url: 'https://www.ilmateenistus.ee/kliima/ajaloolised-ilmaandmed/',
      licence: 'CC BY 4.0',
      licenceUrl: 'https://keskkonnaportaal.ee/et/avaandmed/kliimaandmestik',
      newValues: 'Temperature and snow depth: yesterday. Rainfall: the day before yesterday (summed from hourly values, which are published once a day)',
      corrections:
        'The last 10 days are re-checked on every run. The agency validates its data once a year; those corrections are not yet picked up.',
    },
  ] as const,
  countryFilter: 'Country',
  countryAll: 'All',
  sourceName: { fmi: 'FMI', met: 'MET Norway', smhi: 'SMHI', dmi: 'DMI', imo: 'IMO', kaa: 'Keskkonnaagentuur' },
}

const dateFormat = new Intl.DateTimeFormat('en-GB', { weekday: 'short', day: 'numeric', month: 'long', year: 'numeric' })
const shortDateFormat = new Intl.DateTimeFormat('en-GB', { day: 'numeric', month: 'short' })
const mmFormat = new Intl.NumberFormat('en-GB', { minimumFractionDigits: 1, maximumFractionDigits: 1 })

// API dates are plain YYYY-MM-DD; parse at noon UTC so no timezone can shift the day.
const parse = (iso: string) => new Date(`${iso}T12:00:00Z`)

export const formatDate = (iso: string) => dateFormat.format(parse(iso))

// A fetch time (ISO timestamp) in the viewer's own time zone, e.g. "26 Sept, 11:05".
const timestampFormat = new Intl.DateTimeFormat('en-GB', { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' })
export const formatTimestamp = (iso: string) => timestampFormat.format(new Date(iso))
export const formatShortDate = (iso: string) => shortDateFormat.format(parse(iso))

// Flag texts: rain and snow are flagged only when unusually high, temperature either way.
export const suspectShort = (p: Parameter) => (p.startsWith('temp_') ? t.suspectTempShort : t.suspectShort)
export const suspectLong = (p: Parameter) => (p.startsWith('temp_') ? t.suspectTempLong : t.suspectLong)
export const suspectLegend = (p: Parameter) => (p.startsWith('temp_') ? t.suspectTempLegend : t.suspectLegend)
const cmFormat = new Intl.NumberFormat('en-GB', { maximumFractionDigits: 0 })
const celsiusFormat = new Intl.NumberFormat('en-GB', { minimumFractionDigits: 1, maximumFractionDigits: 1 })

export const formatMm = (mm: number | null) => (mm === null ? t.noData : `${mmFormat.format(mm)} mm`)
export const formatCm = (cm: number | null) => (cm === null ? t.noData : `${cmFormat.format(cm)} cm`)
// A true minus sign (−), not a hyphen, for negative temperatures.
export const formatCelsius = (c: number | null) => (c === null ? t.noData : `${celsiusFormat.format(c).replace('-', '−')} °C`)
export const formatValue = (parameter: Parameter, value: number | null) =>
  parameter === 'snow_depth' ? formatCm(value) : parameter === 'precipitation' ? formatMm(value) : formatCelsius(value)
