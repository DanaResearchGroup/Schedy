# Example input files

Schedy takes two files each year. This folder holds a working example of each, in
the exact format the app expects, so you can compare your real files against
something known-good.

| File | What it is |
| --- | --- |
| `skeleton-example.xlsx` | The **skeletal schedule** — the university's registration export |
| `courses-of-interest.csv` | The **courses of interest** — the list you maintain by hand |
| `courses-of-interest-bare.csv` | The same list in the minimal accepted shape |
| `courses-of-interest.xlsx` | The same list as an Excel file |
| `generate.py` | Rebuilds the two `.xlsx` files; the readable source for what's in them |

Everything here is invented — no real course offerings, no real staff.

---

## 1. The skeletal schedule (from the university)

An `.xlsx` registration export, downloaded as-is. You never edit it. It covers the
whole university — thousands of rows — and Schedy keeps only the courses on your
interest list.

**Columns are found by their Hebrew header text, never by position.** Reorder them,
insert new ones, delete ones you don't have — the import still works. Only the
course-number column `מקצוע` is truly required; without it the file is rejected.

### Columns Schedy understands

| Header | Becomes | Notes |
| --- | --- | --- |
| `מקצוע` | course number | **Required.** Eight digits, leading zeros kept |
| `תיאור מקצוע עברית` | Hebrew name | |
| `תיאור מקצוע אנגלית` | English name | |
| `תיאור חבילת רישום` | group code | The leading token (`SE011`, `קב012`) becomes the group |
| `סוג אירוע D` | session type | `הרצאה` → lecture, `תרגול`/`תרגיל` → exercise, `מעבדה` → lab |
| `ראשון` … `שבת` | day + time | The one day column holding a `HH:MM-HH:MM` range wins |
| `חדר` | room | |
| `פקולטה` | faculty | |
| `שפת הוראת אירוע` | language | |
| `אדם מוקצה` | assigned person | The person's **name** |

Every other named column is kept too, and shown in the review screen when you
expand a row: `בניין`, `רמה אקדמית`, `שפת הוראת מקצוע`, `שעות הוראה בשבוע`,
`תכנון מרכזי`, `סטאטוס אישור חדר`, the UG/GR registration and waitlist counts,
`קיבולת חבילת רישום מוסמכים`, `תאריך מועד א`/`תאריך מועד ב`/`תאריך בחן`,
`הצגת מקצוע בקטלוג`, `מקצוע בעשרה`, and the three `הערה לסמסטר` notes.

Dates come out as `YYYY-MM-DD` whether the cell holds real dates or text.

### Two columns are deliberately discarded

`אדם מוקצה (מספר עובד)` and `אדם מוקצה (ת.ז.)` — an employee number and a national
ID. They carry no scheduling meaning, so Schedy drops them at the parser and never
writes them to its database. The assigned person's name is kept.

### Times and the ⚓ anchor

A row anchors as a fixed placement only when it lands on Schedy's grid: a weekday
Sun–Thu, starting at 08:30 plus a whole number of hours. `01040031` in the example
starts at **09:00** on purpose — it imports fine, but unanchored, so you can see
what a row needing a manual fix looks like.

---

## 2. The courses of interest (maintained by you)

The few dozen course numbers the department actually cares about. This list is what
filters the skeleton: **a course not on this list is not imported.** It changes only
slightly year to year, so keep the file, edit a couple of lines, reload it.

CSV or Excel, both accepted (`.xlsx`/`.xlsm` — a pre-2007 `.xls` is refused with a
note to re-save it). The headed form:

```csv
number,name
00540315,תרמודינמיקה א׳
00540319,תופעות מעבר
01040031,חשבון אינפיניטסימלי 1
```

Only `number` matters. `name` is a comment to help you read the file — Schedy shows
the real name from the skeleton.

**Header aliases.** The number column may be called `number`, `course_number`,
`course`, `no`, `#`, `מקצוע`, `מספר` or `מספר מקצוע`. The name column may be
`name`, `name_he`, `name_en`, `course_name`, `title`, `description`, `שם`,
`שם מקצוע`, `תיאור` or `תיאור מקצוע`. Column order doesn't matter.

**Or skip the header entirely** — a bare list of numbers works
(`courses-of-interest-bare.csv`):

```csv
00540315
00540319
01040031
```

Blank lines are ignored and repeated numbers are collapsed.

### Leading zeros

Course numbers are eight digits and the leading zeros are part of them. Excel
strips them: open `00540315` and save, and the cell becomes `540315`.

Schedy repairs this on import — a purely numeric value shorter than eight digits is
padded back out — so an Excel-mangled file still matches. To keep your own file
clean, format the number column as **Text** in Excel (`generate.py` does this for
the example).

---

## 3. What the two files produce together

Feeding these examples in gives:

```
skeleton-example.xlsx      8 rows, 5 courses
courses-of-interest.csv    3 numbers
                           ↓
                           6 rows kept
```

| Course | Kept | Why |
| --- | --- | --- |
| `00540315` תרמודינמיקה א׳ | 4 rows | On the list — lecture, two exercise groups, one lab |
| `00540319` תופעות מעבר | 1 row | On the list — lecture only |
| `01040031` חשבון אינפיניטסימלי 1 | 1 row | On the list — imports unanchored (09:00 start) |
| `00940411` הסתברות ת׳ | — | Not on the list |
| `02340114` מבוא למדעי המחשב | — | Not on the list |

Try it in the app: **Checklist** tab → import `courses-of-interest.csv`, then
**Import** tab → drop `skeleton-example.xlsx`. Expand any row to see its full
record. Clear the interest list and re-import, and you get zero rows plus a prompt
to load the list first — that is the intended behaviour, not a failure.
