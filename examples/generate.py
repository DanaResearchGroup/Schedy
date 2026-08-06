"""Rebuild the example input files.

The .xlsx examples are binaries, so they are generated rather than committed by
hand — this script is the readable source for what is inside them. Run it after
editing anything here:

    python examples/generate.py

Everything below is invented. Real staff names never appear in this folder, and
the two identity columns of the real export (employee number, national ID) are
written empty here and dropped by the parser regardless.
"""

from __future__ import annotations

import csv
import os
from datetime import date

import openpyxl

HERE = os.path.dirname(os.path.abspath(__file__))

# ---------------------------------------------------------------------------
# 1. The skeletal schedule — the university's registration export.
#
# These are the real column headers, in the real order, taken verbatim from the
# Technion file. The parser locates columns by this text, never by position.
# ---------------------------------------------------------------------------
SKELETON_HEADER = [
    "מקצוע",                          # course number            -> course_number
    "תיאור מקצוע עברית",               # Hebrew name              -> name_he
    "הערה לסמסטר",                     #                          -> details
    "הערה לסמסטר2",                    #                          -> details
    "הערה לסמסטר3",                    #                          -> details
    "תיאור חבילת רישום",               # registration package     -> package/group_code
    "סוג אירוע D",                     # event type               -> event_type
    "ראשון", "שני", "שלישי", "רביעי", "חמישי", "שישי", "שבת",   # day columns -> day/time
    "חדר",                            # room                     -> room
    "בניין",                          # building                 -> details
    "תכנון מרכזי",                     #                          -> details
    "שפת הוראת אירוע",                 # event language           -> language
    "שפת הוראת מקצוע",                 # course language          -> details
    "שעות הוראה בשבוע",                # weekly hours             -> details
    "פקולטה",                         # faculty                  -> faculty
    "",                               # (unnamed column in the real export)
    "קיבולת חבילת רישום מוסמכים",
    "מספר רשומים UG", "מספר בקשות רישום UG", "מספר רשימת המתנה UG",
    'מספר רשומים UG – סה"כ', 'מספר בקשות רישום UG – סה"כ',
    'מספר רשימת המתנה UG – סה"כ',
    "מספר רשומים GR", "מספר בקשות רישום GR",
    'מספר רשומים GR – סה"כ', 'מספר בקשות רישום GR – סה"כ',
    "תאריך מועד א", "תאריך בחן", "תאריך מועד ב",
    "אדם מוקצה (מספר עובד)",           # employee number          -> DROPPED
    "אדם מוקצה (ת.ז.)",                # national ID              -> DROPPED
    "אדם מוקצה",                      # assigned person (name)   -> person
    "הצגת מקצוע בקטלוג",
    "מקצוע בעשרה",
    "סטאטוס אישור חדר",
    "תיאור מקצוע אנגלית",              # English name             -> name_en
    "רמה אקדמית",
]

_DAY_INDEX = {"sun": 0, "mon": 1, "tue": 2, "wed": 3, "thu": 4, "fri": 5, "sat": 6}


def skeleton_row(number, name_he, name_en, package, event_type, *, day=None,
                 time="", room="", building="", person="", faculty="הנדסה כימית",
                 hours=3, registered=0, exam_a=None, level="1", note=""):
    """One event row, filled positionally against SKELETON_HEADER."""
    days = ["", "", "", "", "", "", ""]
    if day is not None:
        days[_DAY_INDEX[day]] = time
    return [
        number, name_he, note, "", "",
        package, event_type,
        *days,
        room, building, "", "HE", "HE", hours, faculty, "",
        "60",
        registered, registered, 0, registered, registered, 0,
        0, 0, 0, 0,
        exam_a, None, None,
        "", "", person,          # employee no. / national ID left empty on purpose
        "כן", "", "מאושר",
        name_en, level,
    ]


# Five courses. Two are in the interest list, two are not (they must be filtered
# away on import), and one — 01040031 — is in the list but has a non-grid time so
# it imports without an anchor.
SKELETON_ROWS = [
    # 00540315 — in the list: a lecture, two exercise groups, and a lab.
    skeleton_row("00540315", "תרמודינמיקה א׳", "Thermodynamics A",
                 "SE011 תרמודינמיקה א׳", "הרצאה", day="sun", time="09:30-11:30",
                 room="אולם 1", building="בניין הנדסה כימית", person="מרצה א׳",
                 hours=4, registered=68, exam_a=date(2026, 2, 11)),
    skeleton_row("00540315", "תרמודינמיקה א׳", "Thermodynamics A",
                 "קב011 תרמודינמיקה א׳", "תרגול", day="tue", time="12:30-13:30",
                 room="כיתה 3", building="בניין הנדסה כימית", person="מתרגל א׳",
                 hours=1, registered=34, exam_a=date(2026, 2, 11)),
    skeleton_row("00540315", "תרמודינמיקה א׳", "Thermodynamics A",
                 "קב012 תרמודינמיקה א׳", "תרגול", day="wed", time="10:30-11:30",
                 room="כיתה 4", building="בניין הנדסה כימית", person="מתרגל ב׳",
                 hours=1, registered=34, exam_a=date(2026, 2, 11)),
    skeleton_row("00540315", "תרמודינמיקה א׳", "Thermodynamics A",
                 "מע011 תרמודינמיקה א׳", "מעבדה", day="thu", time="13:30-15:30",
                 room="מעבדה 2", building="בניין הנדסה כימית", person="מתרגל ג׳",
                 hours=2, registered=22, exam_a=date(2026, 2, 11)),

    # 00540319 — in the list: lecture only.
    skeleton_row("00540319", "תופעות מעבר", "Transport Phenomena",
                 "SE021 תופעות מעבר", "הרצאה", day="mon", time="08:30-11:30",
                 room="אולם 6", building="בניין הנדסה כימית", person="מרצה ב׳",
                 hours=3, registered=71, exam_a=date(2026, 2, 18),
                 note="נדרש אישור ועדת הוראה"),

    # 01040031 — in the list, but starts at 09:00: off the 08:30 + whole-hour
    # grid, so it imports unanchored and the planner fixes the time by hand.
    skeleton_row("01040031", "חשבון אינפיניטסימלי 1", "Calculus 1",
                 "SE101 חשבון אינפיניטסימלי 1", "הרצאה", day="tue",
                 time="09:00-11:00", room="אולם מתמטיקה", building="בניין אולמן",
                 person="מרצה ג׳", faculty="מתמטיקה", hours=2, registered=210,
                 exam_a=date(2026, 2, 4)),

    # 00940411 / 02340114 — NOT in the interest list. Both must vanish on import.
    skeleton_row("00940411", "הסתברות ת׳", "Probability (Ie)",
                 "SE011 הסתברות ת׳", "הרצאה", day="tue", time="09:30-12:30",
                 faculty="מדעי הנתונים", person="מרצה ד׳", hours=3),
    skeleton_row("02340114", "מבוא למדעי המחשב", "Introduction to CS",
                 "SE011 מבוא למדעי המחשב", "הרצאה", day="wed", time="14:30-16:30",
                 faculty="מדעי המחשב", person="מרצה ה׳", hours=3),
]

# ---------------------------------------------------------------------------
# 2. The courses-of-interest list — the file maintained by hand.
# ---------------------------------------------------------------------------
INTEREST = [
    ("00540315", "תרמודינמיקה א׳"),
    ("00540319", "תופעות מעבר"),
    ("01040031", "חשבון אינפיניטסימלי 1"),
]


def write_csv(path, rows):
    with open(path, "w", newline="", encoding="utf-8-sig") as fh:
        csv.writer(fh).writerows(rows)
    print("wrote", os.path.relpath(path, HERE))


def write_xlsx(path, rows, *, text_columns=()):
    wb = openpyxl.Workbook()
    ws = wb.active
    for row in rows:
        ws.append(list(row))
    # Course numbers must stay text, or Excel eats their leading zeros the next
    # time the file is opened. (The importer repairs this too — see
    # coi_io.normalize_number — but a correct example file shouldn't rely on it.)
    for col in text_columns:
        for cell in ws[col]:
            cell.number_format = "@"
    wb.save(path)
    print("wrote", os.path.relpath(path, HERE))


def main():
    write_xlsx(os.path.join(HERE, "skeleton-example.xlsx"),
               [SKELETON_HEADER, *SKELETON_ROWS], text_columns=("A",))

    write_csv(os.path.join(HERE, "courses-of-interest.csv"),
              [["number", "name"], *INTEREST])

    write_csv(os.path.join(HERE, "courses-of-interest-bare.csv"),
              [[number] for number, _ in INTEREST])

    write_xlsx(os.path.join(HERE, "courses-of-interest.xlsx"),
               [["number", "name"], *INTEREST], text_columns=("A",))


if __name__ == "__main__":
    main()
