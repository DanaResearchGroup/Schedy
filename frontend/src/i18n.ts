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
  reset: { he: "איפוס", en: "Reset" },
  resetHint: {
    he: "מוחק את כל הנתונים ומתחיל מחדש",
    en: "Delete all data and start over",
  },
  resetConfirm: {
    he: "לאפס את הסמסטר {term}?\n\nכל נתוני הסמסטר יימחקו: קטלוג הקורסים, אילוצי "
      + "הזמינות, לוח הסמסטר, השלד המיובא והמערכת הנוכחית.\n\n"
      + "סמסטרים אחרים, רשימת הסגל ומערכות שנשמרו (לשונית \"מערכות שמורות\") יישארו.\n\n"
      + "לא ניתן לבטל פעולה זו.",
    en: "Reset {term}?\n\nThis deletes the term's data: the course catalog, "
      + "availability, the semester calendar, the imported skeleton, and the "
      + "current schedule.\n\nOther terms, the faculty registry and saved "
      + "schedules (Schedules tab) are kept.\n\nThis cannot be undone.",
  },
  resetDone: { he: "נתוני הסמסטר נמחקו", en: "The term's data was deleted" },
  term: { he: "סמסטר", en: "Term" },
  winter: { he: "חורף", en: "Winter" },
  spring: { he: "אביב", en: "Spring" },
  newTerm: { he: "סמסטר חדש…", en: "New term…" },
  newTermPrompt: {
    he: "שנה אקדמית חדשה (למשל 2027-28):",
    en: "New academic year (e.g. 2027-28):",
  },
  newTermSemester: {
    he: "איזה סמסטר? הקלד חורף או אביב:",
    en: "Which semester? Type winter or spring:",
  },
  semesterUnrecognised: {
    he: "לא זוהה סמסטר. הקלד חורף או אביב — לא בוצע שינוי.",
    en: "That is not a semester I recognise. Type winter or spring — nothing was changed.",
  },
  renameTerm: { he: "שנה שם…", en: "Rename…" },
  renameTermHint: {
    he: "תיקון השנה האקדמית או הסמסטר של הסמסטר הנוכחי",
    en: "Correct the academic year or semester of the current term",
  },
  published: { he: "פורסם", en: "Published" },
  publish: { he: "פרסם וקבע", en: "Publish & freeze" },
  publishHint: {
    he: "מקבע את מערכת התואר הראשון והקורסים המשותפים — יום, שעה וחדר — "
      + "כדי שאפשר יהיה להוסיף קורסי תואר שני מבלי להזיז דבר",
    en: "Freeze the undergraduate and joint week — day, hour and room — so "
      + "graduate courses can be added later without moving anything",
  },
  publishConfirm: {
    he: "לפרסם ולקבע את {term}?\n\nכל שיעורי התואר הראשון והקורסים המשותפים "
      + "יינעלו ליום, לשעה ולחדר שלהם. קורסי התואר השני יישארו חופשיים לשלב השני."
      + "\n\nניתן לבטל בהמשך בעזרת \"בטל פרסום\".",
    en: "Publish and freeze {term}?\n\nEvery undergraduate and joint session is "
      + "locked to its day, hour and room. Graduate courses stay free for "
      + "phase 2.\n\nYou can undo this later with \"Unpublish\".",
  },
  publishDone: { he: "{n} שיעורים נקבעו", en: "{n} sessions frozen" },
  unpublish: { he: "בטל פרסום", en: "Unpublish" },
  unpublishConfirm: {
    he: "לבטל את פרסום {term}?\n\nהמערכת תשוחרר והפותר יוכל להזיז שיעורים "
      + "שכבר נמסרו לסטודנטים.",
    en: "Unpublish {term}?\n\nThe week is released, and the solver may move "
      + "sessions the students have already been given.",
  },
  publishedMissing: {
    he: "שיעורים שפורסמו ואינם קיימים עוד בקטלוג: {ids}. הם נשמטו מהמערכת הקפואה.",
    en: "Published sessions the catalog no longer has: {ids}. They have dropped "
      + "out of the frozen schedule.",
  },
  publishedConflict: {
    he: "השלד המיובא מבקש זמן אחר עבור שיעורים שפורסמו: {ids}. "
      + "הזמן שפורסם הוא שנשמר.",
    en: "The imported skeleton wants a different time for published sessions: "
      + "{ids}. The published time is what holds.",
  },
  confirmTermName: {
    he: "סקדי שיער שהנתונים הקיימים שייכים לסמסטר {term}. "
      + "אשר או תקן זאת בעזרת \"שנה שם…\".",
    en: "Schedy guessed the existing data belongs to {term}. "
      + "Confirm or correct it with \"Rename…\".",
  },
  offered: { he: "ניתן הסמסטר", en: "Offered this semester" },
  notOffered: { he: "לא ניתן הסמסטר", en: "Not offered" },
  offeredHint: {
    he: "בטל סימון כדי לדלג על הקורס בסמסטר זה מבלי למחוק אותו מהקטלוג",
    en: "Uncheck to skip this course this semester without deleting it from the catalog",
  },
  skipReason: { he: "סיבת הדילוג", en: "Reason for skipping" },
  skipReasonPlaceholder: {
    he: "למשל: פרופ׳ כהן בשבתון תשפ״ו",
    en: "e.g. Prof. Cohen on sabbatical 2026",
  },
  showNotOffered: { he: "הצג קורסים שאינם ניתנים", en: "Show courses not offered" },
  notOfferedCount: { he: "אינם ניתנים הסמסטר", en: "not offered this semester" },
  notTeachingGroup: {
    he: "אינם מלמדים הסמסטר (נשמר)",
    en: "Not teaching this semester (kept)",
  },
  notTeachingNote: {
    he: "אדם זה אינו מלמד בסמסטר זה — האילוצים שלו נשמרים אך אינם משפיעים על השיבוץ.",
    en: "This person isn't teaching this semester — their blocks are kept but do not affect the solve.",
  },
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
  credit: { he: "נקודות זכות", en: "Credit points" },
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
  byRoom: { he: "לפי חדר", en: "By room" },
  byLecturer: { he: "לפי מרצה", en: "By lecturer" },
  filterCourses: { he: "קורסים", en: "Courses" },
  allCourses: { he: "כל הקורסים", en: "All courses" },
  otherDept: { he: "פקולטה אחרת", en: "Other faculty" },
  filterAudience: { he: "קהל", en: "Audience" },
  allAudiences: { he: "כל הקהלים", en: "All audiences" },
  gradCourses: { he: "תארים מתקדמים", en: "Graduate" },
  allRooms: { he: "כל החדרים", en: "All rooms" },
  allLecturers: { he: "כל המרצים", en: "All lecturers" },
  clearFilters: { he: "נקה סינון", en: "Clear filters" },
  shownOfTotal: { he: "מפגשים מוצגים מתוך הכל", en: "sessions shown of the full week" },
  layoutGrid: { he: "רשת", en: "Grid" },
  layoutRooms: { he: "חדרים", en: "Rooms" },
  undo: { he: "בטל", en: "Undo" },
  redo: { he: "בצע שוב", en: "Redo" },
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
  weekStartsOn: { he: "שבוע הלימודים מתחיל ביום", en: "Teaching week starts on" },
  weekStartsHint: {
    he:
      "הסמסטר נפתח באמצע השבוע, ולכן סדר ״הרצאה לפני תרגול״ נמדד מהיום הזה " +
      "ולא מיום ראשון.",
    en:
      "The semester opens mid-week, so lecture-before-exercise order is measured " +
      "from this day rather than from Sunday.",
  },
  causeTemplateOrder: { he: "סדר קבוע בכל שבוע", en: "Every week" },
  causeSubstitution: { he: "בעקבות החלפת יום", en: "Day substitution" },
  weeksAffected: { he: "שבועות", en: "weeks" },
  loadSample: { he: "טען קטלוג לדוגמה", en: "Load sample catalog" },
  exportCatalog: { he: "ייצוא קטלוג", en: "Export catalog" },
  importCatalogLabel: { he: "ייבוא קטלוג", en: "Import catalog" },
  downloadTemplate: { he: "הורד תבנית", en: "Download template" },
  importCatalogConfirm: {
    he: "ייבוא קטלוג יחליף את כל הקורסים הקיימים. להמשיך?",
    en: "Importing a catalog replaces all current courses. Continue?",
  },
  catalogImported: { he: "יובאו", en: "Imported" },
  blackoutLegend: { he: "חלון חסום", en: "Blackout" },
  externalLegend: { he: "קורס חיצוני", en: "External" },
  fixedTag: { he: "עוגן (שלד)", en: "anchor (skeleton)" },
  pdfGrid: { he: "PDF מערכת", en: "PDF grid" },
  pdfList: { he: "PDF רשימה", en: "PDF list" },
  pinnedHint: {
    he: "⚓ שורות עם יום ושעה מהשלד מעוגנות עבור הפותר (אפשר עדיין להזיז ידנית).",
    en: "⚓ rows with a skeleton day + time are anchored for the solver (you can still move them manually).",
  },
  emptyCatalog: {
    he: "הקטלוג ריק — הוסף קורס או טען קטלוג לדוגמה כדי להתחיל",
    en: "Catalog is empty — add a course or load the sample catalog to get started",
  },
  tabSchedules: { he: "שמורים", en: "Saved" },
  tabChecklist: { he: "בדיקת קורסים", en: "Course check" },
  tabPeople: { he: "סגל", en: "Faculty" },
  peopleHint: {
    he: "הגדר את חברי הסגל והמתרגלים פעם אחת, כדי למנוע כפילויות בשמות ולשייך אילוצים לאדם הנכון.",
    en: "Define lecturers and TAs once, so names don't get spelled differently and constraints attach to the right person.",
  },
  addPerson: { he: "הוסף איש סגל", en: "Add person" },
  personName: { he: "שם", en: "Name" },
  kindCol: { he: "תפקיד", en: "Type" },
  kindFaculty: { he: "חבר/ת סגל", en: "Faculty member" },
  kindGrad: { he: "סטודנט/ית מחקר", en: "Grad student" },
  importFromCourses: { he: "ייבא מהקורסים", en: "Import from courses" },
  noPeopleYet: {
    he: "טרם הוגדר סגל — הוסף אנשים או ייבא מהקורסים.",
    en: "No faculty defined yet — add people or import from courses.",
  },
  coiTitle: { he: "קורסים שלנו לבדיקה", en: "Our courses to verify" },
  coiHint: {
    he: "רשימת מספרי הקורסים שמעניינים אותנו — היא שמסננת את השלד בייבוא: קורס שאינו ברשימה לא ייובא. משתנה מעט משנה לשנה, אז נוח לטעון אותה מקובץ.",
    en: "The course numbers we care about — this list is what filters the skeleton on import: a course not listed is not imported. It changes only slightly year to year, so keep it in a file and load it.",
  },
  addNumber: { he: "הוסף מספר קורס", en: "Add course number" },
  coiImport: { he: "טען קובץ קורסים", en: "Load courses file" },
  coiExport: { he: "ייצא רשימה", en: "Export list" },
  coiTemplate: { he: "הורד תבנית", en: "Download template" },
  coiImportConfirm: {
    he: "טעינת קובץ תחליף את הרשימה הנוכחית. להמשיך?",
    en: "Loading a file replaces the current list. Continue?",
  },
  coiFileHint: {
    he: "CSV או Excel, עם כותרת number,name או פשוט רשימת מספרים. אפסים מובילים מושלמים אוטומטית.",
    en: "CSV or Excel, with a number,name header or just a bare list of numbers. Leading zeros are restored automatically.",
  },
  coiLoaded: { he: "נטענו {n} קורסים", en: "Loaded {n} courses" },
  importNeedsCoi: {
    he: "השלד נקרא, אך רשימת הקורסים שלנו ריקה — לכן לא יובאה אף שורה. טען את הרשימה בלשונית הבדיקה ואז ייבא שוב.",
    en: "The skeleton was read, but our courses-of-interest list is empty — so no rows were imported. Load the list in the Checklist tab, then import again.",
  },
  showDetails: { he: "הצג את כל פרטי השורה", en: "Show the row's full record" },
  checkImportFirst: {
    he: "ייבא שלד (בלשונית ייבוא) כדי לבדוק זמינות.",
    en: "Import a skeleton (Import tab) to check availability.",
  },
  checkEmpty: { he: "הוסף מספרי קורס כדי לבדוק.", en: "Add course numbers to check." },
  checkMissing: { he: "קורסים חסרים מהשלד!", en: "Courses missing from the skeleton!" },
  checkAllAvailable: {
    he: "כל הקורסים נמצאים בשלד ✓",
    en: "All courses are available in the skeleton ✓",
  },
  present: { he: "נמצא", en: "present" },
  missing: { he: "חסר", en: "missing" },
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
    he: "כל מערכת נשמרת כקובץ נפרד בתיקייה זו.",
    en: "Each schedule is saved as its own file in this folder.",
  },
  savesFolderRoot: {
    he: "ניתן לבחור כל תיקייה תחת:",
    en: "You can choose any folder under:",
  },
  savesFolderRejected: {
    he: "התיקייה שהוגדרה קודם נמצאת מחוץ לתחום המותר ולכן אינה בשימוש. השמירות שבה לא נמחקו:",
    en: "The folder configured earlier lies outside the permitted root and is not in use. The saves in it were not deleted:",
  },
  change: { he: "שנה", en: "Change" },
  loadConfirm: {
    he: "טעינה תחליף את המצב הנוכחי (לא נשמר). להמשיך?",
    en: "Loading replaces the current working state (unsaved). Continue?",
  },
  deleteConfirm: { he: "למחוק מערכת שמורה זו?", en: "Delete this saved schedule?" },
  sessionsShort: { he: "מפגשים", en: "sessions" },
  hardShort: { he: "קשות", en: "hard" },
  compare: { he: "השוואה", en: "Compare" },
  compareHint: { he: "בחר שתי מערכות שמורות כדי לראות מה השתנה", en: "Pick two saved schedules to see what changed" },
  movedLabel: { he: "הוזזו", en: "moved" },
  addedLabel: { he: "נוספו", en: "added" },
  removedLabel: { he: "הוסרו", en: "removed" },
  unchangedLabel: { he: "ללא שינוי", en: "unchanged" },
  noChanges: { he: "אין הבדלים בין השתיים", en: "No differences between the two" },
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

// Labels for the pass-through skeleton columns (parser._DETAIL_HEADERS). The
// review screen renders whatever `details` keys a row happens to carry, so an
// unlabelled key falls back to its slug rather than disappearing.
export const DETAIL_LABEL: Record<string, Record<Lang, string>> = {
  // First-class row fields shown alongside the pass-through ones.
  person: { he: "אדם מוקצה", en: "Assigned person" },
  faculty: { he: "פקולטה", en: "Faculty" },
  language: { he: "שפת הוראת אירוע", en: "Event language" },
  building: { he: "בניין", en: "Building" },
  academic_level: { he: "רמה אקדמית", en: "Academic level" },
  course_language: { he: "שפת הוראת מקצוע", en: "Course language" },
  weekly_hours: { he: "שעות הוראה בשבוע", en: "Hours per week" },
  central_planning: { he: "תכנון מרכזי", en: "Central planning" },
  room_approval_status: { he: "סטאטוס אישור חדר", en: "Room approval" },
  registered_ug: { he: "רשומים UG", en: "Registered UG" },
  requests_ug: { he: "בקשות רישום UG", en: "Requests UG" },
  waitlist_ug: { he: "רשימת המתנה UG", en: "Waitlist UG" },
  registered_ug_total: { he: 'רשומים UG סה"כ', en: "Registered UG (total)" },
  requests_ug_total: { he: 'בקשות רישום UG סה"כ', en: "Requests UG (total)" },
  waitlist_ug_total: { he: 'רשימת המתנה UG סה"כ', en: "Waitlist UG (total)" },
  registered_gr: { he: "רשומים GR", en: "Registered GR" },
  requests_gr: { he: "בקשות רישום GR", en: "Requests GR" },
  registered_gr_total: { he: 'רשומים GR סה"כ', en: "Registered GR (total)" },
  requests_gr_total: { he: 'בקשות רישום GR סה"כ', en: "Requests GR (total)" },
  grad_package_capacity: { he: "קיבולת חבילת מוסמכים", en: "Grad package capacity" },
  exam_a_date: { he: "מועד א", en: "Exam A" },
  exam_b_date: { he: "מועד ב", en: "Exam B" },
  quiz_date: { he: "בחן", en: "Quiz" },
  show_in_catalog: { he: "מוצג בקטלוג", en: "Shown in catalog" },
  course_in_tens: { he: "מקצוע בעשרה", en: "Course in tens" },
  semester_note: { he: "הערה לסמסטר", en: "Semester note" },
  semester_note_2: { he: "הערה לסמסטר 2", en: "Semester note 2" },
  semester_note_3: { he: "הערה לסמסטר 3", en: "Semester note 3" },
};

export function detailLabel(key: string, lang: Lang): string {
  return DETAIL_LABEL[key]?.[lang] ?? key;
}

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

export const t = (
  key: keyof typeof STRINGS, lang: Lang, vars?: Record<string, string>,
): string => {
  const s = STRINGS[key][lang];
  return vars ? s.replace(/\{(\w+)\}/g, (m, k) => vars[k] ?? m) : s;
};

// "2026-27-winter" reads as "2026-27 Winter" / "2026-27 חורף". The id is the
// backend's key; this is the only place it is made human.
export function termLabel(id: string, lang: Lang): string {
  const [year, , semester] = [id.slice(0, id.lastIndexOf("-")), "", id.slice(id.lastIndexOf("-") + 1)];
  const name = semester === "winter" || semester === "spring"
    ? t(semester, lang) : semester;
  return `${year} ${name}`;
}

export function minutesToHHMM(m: number | null | undefined): string {
  if (m == null) return "";
  return `${String(Math.floor(m / 60)).padStart(2, "0")}:${String(m % 60).padStart(2, "0")}`;
}

export function hhmmToMinutes(s: string): number | null {
  const m = /^(\d{1,2}):(\d{2})$/.exec(s.trim());
  if (!m) return null;
  return parseInt(m[1], 10) * 60 + parseInt(m[2], 10);
}
