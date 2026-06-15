// Minimal bilingual strings + RTL handling. Hebrew is the primary planner
// language; English is the fallback. Switching to Hebrew flips the document to RTL.

export type Lang = "he" | "en";

export const STRINGS = {
  title: { he: "סקדי — מערכת שיבוץ", en: "Schedy — Department Scheduler" },
  catalog: { he: "קטלוג קורסים", en: "Course catalog" },
  solve: { he: "פתור", en: "Solve" },
  solving: { he: "פותר…", en: "Solving…" },
  schedule: { he: "מערכת שעות", en: "Weekly schedule" },
  violations: { he: "התנגשויות", en: "Violations" },
  exportCsv: { he: "ייצוא CSV", en: "Export CSV" },
  exportPdf: { he: "ייצוא PDF", en: "Export PDF" },
  noViolations: { he: "אין התנגשויות קשות", en: "No hard violations" },
  feasible: { he: "תקין", en: "Feasible" },
  infeasible: { he: "לא תקין", en: "Has hard conflicts" },
  addCourse: { he: "הוסף קורס", en: "Add course" },
  editCourse: { he: "עריכת קורס", en: "Edit course" },
  newCourse: { he: "קורס חדש", en: "New course" },
  number: { he: "מספר קורס", en: "Course number" },
  empty: { he: "לא נמצאה מערכת — הוסף קורסים ולחץ פתור", en: "No schedule yet — add courses and Solve" },
  save: { he: "שמור", en: "Save" },
  cancel: { he: "ביטול", en: "Cancel" },
  nameHe: { he: "שם בעברית", en: "Hebrew name" },
  nameEn: { he: "שם באנגלית", en: "English name" },
  programs: { he: "תוכניות", en: "Programs" },
  year: { he: "שנה", en: "Year" },
  role: { he: "סוג", en: "Role" },
  sessions: { he: "מבנה הקורס", en: "Session structure" },
  lectureHours: { he: "שעות הרצאה", en: "Lecture hours" },
  exerciseGroups: { he: "קבוצות תרגול", en: "Exercise groups" },
  exerciseHours: { he: "שעות תרגול", en: "Exercise hours" },
  labHours: { he: "שעות מעבדה", en: "Lab hours" },
  labDays: { he: "ימי מעבדה", en: "Lab days" },
  enrollment: { he: "מספר נרשמים צפוי", en: "Expected enrollment" },
  computerFarm: { he: "דורש חוות מחשבים", en: "Needs computer farm" },
  remote: { he: "מקוון (זום)", en: "Remote (Zoom)" },
  external: { he: "קורס חיצוני (קבוע)", en: "External course (fixed)" },
  placement: { he: "מיקום קבוע", en: "Fixed placement" },
  from: { he: "משעה", en: "From" },
  to: { he: "עד שעה", en: "To" },
  room: { he: "חדר", en: "Room" },
  lecturers: { he: "מרצים (מופרד בפסיק)", en: "Lecturers (comma-separated)" },
  tas: { he: "מתרגלים (מופרד בפסיק)", en: "TAs (comma-separated)" },
  required: { he: "נדרש מספר קורס", en: "Course number is required" },
  tabSchedule: { he: "מערכת", en: "Schedule" },
  tabCatalog: { he: "קטלוג", en: "Catalog" },
  tabImport: { he: "ייבוא", en: "Import" },
  importSkeleton: { he: "ייבוא שלד (XLSX)", en: "Import skeleton (XLSX)" },
  importHint: { he: "בחר קובץ שלד מהטכניון — יסונן לקורסים שבקטלוג", en: "Pick the Technion skeleton — filtered to catalog courses" },
  dropHere: { he: "גרור לכאן קובץ XLSX, או לחץ לבחירה", en: "Drop an XLSX file here, or click to choose" },
  dropToImport: { he: "שחרר כדי לייבא", en: "Release to import" },
  importReplaceHint: { he: "ייבוא חדש מחליף את הנתונים הקיימים", en: "A new import replaces the existing data" },
  clearImport: { he: "נקה ייבוא", en: "Clear import" },
  clearImportConfirm: { he: "למחוק את כל הנתונים המיובאים?", en: "Delete all imported data?" },
  importing: { he: "מייבא…", en: "Importing…" },
  offeredSessions: { he: "מפגשים שנמצאו", en: "Offered sessions" },
  noOffered: { he: "טרם יובא שלד", en: "No skeleton imported yet" },
  view: { he: "תצוגה", en: "View" },
  allSessions: { he: "הכל", en: "All" },
  byCohort: { he: "לפי מחזור", en: "By cohort" },
  byRoom: { he: "לפי חדר", en: "By room" },
  byLecturer: { he: "לפי מרצה", en: "By lecturer" },
  layoutGrid: { he: "רשת", en: "Grid" },
  layoutRooms: { he: "חדרים", en: "Rooms" },
  seats: { he: "מקומות", en: "seats" },
  free: { he: "פנוי", en: "free" },
  parked: { he: "ממתינים לשיבוץ", en: "Parked" },
  parkHint: { he: "גרור מפגש לכאן כדי להוציאו מהחדרים", en: "Drag a session here to set it aside" },
  unplaced: { he: "לא משובצים", en: "unplaced" },
  unplacedHint: { he: "מפגשים שהוצאו מהחדרים — לחץ למעבר לתצוגת חדרים", en: "Sessions set aside — click to open the Rooms view" },
  statRoomsInUse: { he: "חדרים בשימוש", en: "rooms in use" },
  statBooked: { he: "שעות משובצות", en: "booked" },
  statUtilization: { he: "ניצולת", en: "utilization" },
  tooSmall: { he: "קטן מדי לקבוצה זו", en: "too small for this group" },
  needsFarmShort: { he: "דורש חוות מחשבים", en: "needs the computer farm" },
  details: { he: "פרטים", en: "Details" },
  type: { he: "סוג אירוע", en: "Type" },
  day: { he: "יום", en: "Day" },
  time: { he: "שעה", en: "Time" },
  group: { he: "קבוצה", en: "Group" },
  tabAvailability: { he: "זמינות", en: "Availability" },
  person: { he: "סגל", en: "Person" },
  availabilityHint: {
    he: "לחץ על משבצת כדי לסמן שהמרצה/מתרגל אינו זמין באותה שעה. משבצות מסומנות הופכות לאילוץ קשה בפתרון.",
    en: "Click a cell to mark the lecturer/TA as unavailable then. Blocked cells become hard constraints when solving.",
  },
  clearBlocks: { he: "נקה", en: "Clear" },
  saving: { he: "שומר…", en: "Saving…" },
  available: { he: "זמין", en: "Available" },
  unavailable: { he: "לא זמין", en: "Unavailable" },
  noPeople: {
    he: "לא הוגדרו מרצים או מתרגלים בקטלוג",
    en: "No lecturers or TAs defined in the catalog yet",
  },
  tabCalendar: { he: "לוח שנה", en: "Calendar" },
  calendarHint: {
    he: "הגדר את תאריכי הסמסטר, ימים חסומים והחלפות ימים, ואז נתח.",
    en: "Define semester dates, blocked days, and day-substitutions, then Analyze.",
  },
  semesterStart: { he: "תחילת סמסטר", en: "Semester start" },
  semesterEnd: { he: "סוף סמסטר (כולל)", en: "Semester end (inclusive)" },
  blockedDates: { he: "ימים חסומים", en: "Blocked dates" },
  substitutions: { he: "החלפות ימים", en: "Day substitutions" },
  runsAs: { he: "רץ כמו", en: "runs as" },
  addItem: { he: "הוסף", en: "Add" },
  analyze: { he: "נתח", en: "Analyze" },
  analyzing: { he: "מנתח…", en: "Analyzing…" },
  teachingDaysLabel: { he: "ימי לימוד", en: "Teaching days" },
  weeksLabel: { he: "שבועות", en: "Weeks" },
  blockedLabel: { he: "חסומים", en: "Blocked" },
  perWeekday: { he: "ימי לימוד לפי יום", en: "Teaching days per weekday" },
  lostSessions: { he: "מפגשים חסרים", en: "Uneven sessions" },
  orderInversions: { he: "היפוך סדר הרצאה/תרגול", en: "Order inversions" },
  noIssues: { he: "לא נמצאו בעיות", en: "No issues found" },
  solveForDeficits: {
    he: 'הרץ "פתור" לניתוח חוסרים ברמת המפגש',
    en: "Run Solve for per-session deficit analysis",
  },
  deficitLabel: { he: "חוסר", en: "deficit" },
  weekLabel: { he: "שבוע", en: "Week" },
  loadSample: { he: "טען קטלוג לדוגמה", en: "Load sample catalog" },
  blackoutLegend: { he: "חלון חסום", en: "Blackout" },
  externalLegend: { he: "קורס חיצוני", en: "External" },
  fixedTag: { he: "מקובע (שלד)", en: "fixed (skeleton)" },
  pdfGrid: { he: "PDF מערכת", en: "PDF grid" },
  pdfList: { he: "PDF רשימה", en: "PDF list" },
  pinnedHint: {
    he: "🔒 שורות עם יום ושעה מהשלד יקובעו כאילוץ קשה בפתרון.",
    en: "🔒 rows with a skeleton day + time are pinned as a hard constraint when solving.",
  },
  emptyCatalog: {
    he: "הקטלוג ריק — הוסף קורס או טען קטלוג לדוגמה כדי להתחיל",
    en: "Catalog is empty — add a course or load the sample catalog to get started",
  },
  tabSchedules: { he: "שמורים", en: "Saved" },
  saveSchedule: { he: "שמור מערכת נוכחית", en: "Save current schedule" },
  saveAs: { he: "שמור בשם…", en: "Save current as…" },
  scheduleName: { he: "שם המערכת", en: "Schedule name" },
  noteOptional: { he: "הערה (לא חובה)", en: "Note (optional)" },
  savedSchedules: { he: "מערכות שמורות", en: "Saved schedules" },
  noSaved: { he: "אין מערכות שמורות עדיין", en: "No saved schedules yet" },
  load: { he: "טען", en: "Load" },
  rename: { he: "שנה שם", en: "Rename" },
  delete: { he: "מחק", en: "Delete" },
  savesFolder: { he: "תיקיית השמירה", en: "Saves folder" },
  savesFolderHint: {
    he: "כל מערכת נשמרת כקובץ נפרד בתיקייה זו. ניתן להצביע על תיקייה מסונכרנת או כונן רשת.",
    en: "Each schedule is saved as its own file in this folder. Point it at a synced folder or network drive if you like.",
  },
  change: { he: "שנה", en: "Change" },
  loadConfirm: {
    he: "טעינה תחליף את המצב הנוכחי (לא נשמר). להמשיך?",
    en: "Loading replaces the current working state (unsaved). Continue?",
  },
  deleteConfirm: { he: "למחוק מערכת שמורה זו?", en: "Delete this saved schedule?" },
  sessionsShort: { he: "מפגשים", en: "sessions" },
  hardShort: { he: "קשות", en: "hard" },
  saved: { he: "נשמר", en: "Saved" },
  needSolveToSave: {
    he: "פתור מערכת לפני שמירה",
    en: "Solve a schedule before saving",
  },
} as const;

export const ROLE_LABEL: Record<string, Record<Lang, string>> = {
  core: { he: "ליבה", en: "core" },
  elective: { he: "בחירה", en: "elective" },
  replacement: { he: "חלופי", en: "replacement" },
  lab: { he: "מעבדה", en: "lab" },
};

export const DAY_NAMES: Record<Lang, string[]> = {
  en: ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday"],
  he: ["ראשון", "שני", "שלישי", "רביעי", "חמישי"],
};

// Compact weekday labels for dense grids (e.g. per-room boards). Hebrew uses the
// conventional ordinal letters (א=Sun … ה=Thu); English uses two letters to keep
// Tuesday/Thursday distinct.
export const DAY_ABBR: Record<Lang, string[]> = {
  en: ["Su", "Mo", "Tu", "We", "Th"],
  he: ["א", "ב", "ג", "ד", "ה"],
};

export function boxLabel(box: number): string {
  const start = 8 * 60 + 30 + box * 60;
  const end = start + 60;
  const fmt = (m: number) => `${String(Math.floor(m / 60)).padStart(2, "0")}:${String(m % 60).padStart(2, "0")}`;
  return `${fmt(start)}-${fmt(end)}`;
}

export const t = (key: keyof typeof STRINGS, lang: Lang): string => STRINGS[key][lang];

export function minutesToHHMM(m: number | null | undefined): string {
  if (m == null) return "";
  return `${String(Math.floor(m / 60)).padStart(2, "0")}:${String(m % 60).padStart(2, "0")}`;
}

export function hhmmToMinutes(s: string): number | null {
  const m = /^(\d{1,2}):(\d{2})$/.exec(s.trim());
  if (!m) return null;
  return parseInt(m[1], 10) * 60 + parseInt(m[2], 10);
}
