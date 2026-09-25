// All user-facing text (UK English), kept in one place so it can be translated later.
export const t = {
  title: 'Rainfall in Finland',
  subtitle: 'Daily precipitation at FMI weather stations',
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
  fmisid: 'FMI station ID',
  coordinates: 'Coordinates',
  last30Days: 'Last 30 days',
  total: 'Total',
  wetDays: 'Days with rain',
  measurementNote: 'Each daily value is the total from 06:00 UTC on that date to 06:00 UTC the next day.',
  legendTitle: 'Rainfall per day',
  stationsWithData: (withData: number, total: number) => `${withData} of ${total} stations reporting`,
  attribution: 'Data: Finnish Meteorological Institute open data (CC BY 4.0)',
  aboutButton: 'About Rainfall',
  aboutTitle: 'About Rainfall',
  aboutBody:
    'Rainfall shows the daily precipitation measured at Finnish weather stations on a map. Pick a date to see how much it rained where, and select a station for its recent history.',
  aboutDataPrefix: 'Rainfall data is provided by the',
  aboutDataLink: 'Finnish Meteorological Institute (FMI) open data',
  aboutDataSuffix: 'under the CC BY 4.0 licence.',
  aboutDeveloperPrefix: 'Developed by',
  developerName: 'Janne Isosävi',
  developerUrl: 'https://github.com/jisosavi',
  aboutFeedbackPrefix: 'Found a problem or have an idea?',
  aboutFeedbackLink: 'Send feedback on GitHub',
  aboutSourceLink: 'Source code',
  feedbackUrl: 'https://github.com/jisosavi/rainfall/issues/new/choose',
  sourceUrl: 'https://github.com/jisosavi/rainfall',
  fmiOpenDataUrl: 'https://en.ilmatieteenlaitos.fi/open-data',
}

const dateFormat = new Intl.DateTimeFormat('en-GB', { weekday: 'short', day: 'numeric', month: 'long', year: 'numeric' })
const shortDateFormat = new Intl.DateTimeFormat('en-GB', { day: 'numeric', month: 'short' })
const mmFormat = new Intl.NumberFormat('en-GB', { minimumFractionDigits: 1, maximumFractionDigits: 1 })

// API dates are plain YYYY-MM-DD; parse at noon UTC so no timezone can shift the day.
const parse = (iso: string) => new Date(`${iso}T12:00:00Z`)

export const formatDate = (iso: string) => dateFormat.format(parse(iso))
export const formatShortDate = (iso: string) => shortDateFormat.format(parse(iso))
export const formatMm = (mm: number | null) => (mm === null ? t.noData : `${mmFormat.format(mm)} mm`)
