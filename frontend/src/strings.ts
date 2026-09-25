// All user-facing text (UK English), kept in one place so it can be translated later.
export const t = {
  title: 'Nordic rainfall',
  subtitle: 'Daily precipitation at weather stations in Finland, Norway and Sweden',
  loading: 'Loading…',
  loadError: 'Could not load rainfall data. Please try again later.',
  noDataYet: 'No rainfall data available yet.',
  noStationsForDate: 'No stations reported on this date.',
  previousDay: 'Previous day',
  nextDay: 'Next day',
  latest: 'Latest',
  chooseDate: 'Date',
  showList: 'List',
  hideList: 'Map only',
  listHeading: 'Stations by rainfall',
  station: 'Station',
  rainfall: 'Rainfall',
  noData: 'No data',
  close: 'Close',
  region: 'Municipality',
  owner: 'Station owner',
  stationId: 'Station ID',
  coordinates: 'Coordinates',
  last30Days: 'Last 30 days',
  total: 'Total',
  wetDays: 'Days with rain',
  measurementNote: 'Each daily value is the total from 06:00 UTC on that date to 06:00 UTC the next day.',
  legendTitle: 'Rainfall per day',
  stationsWithData: (withData: number, total: number) => `${withData} of ${total} stations reporting`,
  attribution: 'Data: FMI, MET Norway and SMHI (CC BY 4.0), processed',
  aboutButton: 'About Rainfall',
  aboutTitle: 'About Rainfall',
  aboutBody:
    'Nordic rainfall shows the daily precipitation measured at weather stations in Finland, Norway and Sweden on a map. Pick a date to see how much it rained where, and select a station for its recent history.',
  aboutDataHeading: 'Data',
  aboutDataIntro: 'Rainfall observations come from the national weather services as open data:',
  aboutDataColumns: { country: 'Country', provider: 'Data provider', stations: 'Stations', licence: 'Licence' },
  aboutStationsNote: 'Stations: number on the date shown on the map.',
  aboutProcessingNote:
    'The data has been processed: values are quality-filtered, aligned to the same daily period (06:00–06:00 UTC), and days without a value are marked as missing.',
  aboutUpdatesHeading: 'Updates',
  aboutUpdatesIntro: (utcTimes: string, localTimes: string) =>
    `Data is fetched twice a day, at ${utcTimes} UTC (${localTimes} your time). Each daily value covers 06:00–06:00 UTC, so yesterday's value can first appear in the morning run.`,
  aboutUpdatesColumns: { country: 'Country', newValues: 'New values', corrections: 'Late values and corrections' },
  aboutProjectHeading: 'Project',
  aboutDeveloperPrefix: 'Developed by',
  developerName: 'Janne Isosävi',
  developerUrl: 'https://github.com/jisosavi',
  aboutFeedbackPrefix: 'Found a problem or have an idea?',
  aboutFeedbackLink: 'Send feedback on GitHub',
  aboutSourceLink: 'Source code',
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
  ] as const,
  countryFilter: 'Country',
  countryAll: 'All',
  countryFinland: 'Finland',
  countryNorway: 'Norway',
  countrySweden: 'Sweden',
  sourceName: { fmi: 'FMI', met: 'MET Norway', smhi: 'SMHI' },
  countryTag: { fmi: 'FI', met: 'NO', smhi: 'SE' },
}

const dateFormat = new Intl.DateTimeFormat('en-GB', { weekday: 'short', day: 'numeric', month: 'long', year: 'numeric' })
const shortDateFormat = new Intl.DateTimeFormat('en-GB', { day: 'numeric', month: 'short' })
const mmFormat = new Intl.NumberFormat('en-GB', { minimumFractionDigits: 1, maximumFractionDigits: 1 })

// API dates are plain YYYY-MM-DD; parse at noon UTC so no timezone can shift the day.
const parse = (iso: string) => new Date(`${iso}T12:00:00Z`)

export const formatDate = (iso: string) => dateFormat.format(parse(iso))
export const formatShortDate = (iso: string) => shortDateFormat.format(parse(iso))
export const formatMm = (mm: number | null) => (mm === null ? t.noData : `${mmFormat.format(mm)} mm`)
