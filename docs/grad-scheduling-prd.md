# PRD — Graduate courses, course levels, and per-term scheduling

> Status: awaiting review — **no code written**
> Supersedes nothing; extends `PRD.md`, which assumes a single implicit semester.
> Design settled in a design interview; every decision below was chosen explicitly.

## Problem statement

Three problems, discovered together and inseparable in practice.

**1. Graduate courses have no representation.** `Program` has exactly three
undergraduate tracks and `Cohort` assumes years 1–4. A graduate course cannot be
entered at all without lying about its audience.

**2. Graduate courses obey a different clash rule.** Undergraduate electives may
overlap — a student who cannot take both is a soft penalty the planner reviews
(`elective_vs_elective`, weight 500). Graduate courses may **not** overlap each
other, nor joint undergraduate/graduate courses. This is a hard rule, and it must
also hold against graduate courses taught by other faculties.

**3. The undergraduate schedule must publish before graduate courses are known.**
The department finalises and publishes the undergraduate timetable months before
the graduate offering is settled. Graduate courses are appended later and must not
disturb anything already published — which requires knowing *which* arrangement was
published, and therefore requires Schedy to understand academic years at all.

## Terminology

**Academic year** — `2025-26`, `2026-27`. A new first-class term.

**Semester** — `Winter` or `Spring`. The department runs Schedy in production twice
a year, once per semester.

**Term** — the pair, e.g. `2026-27 Spring`. The unit everything is scoped by.

**Level** — `UG`, `joint`, or `grad`. A property of a course, distinct from `role`
(core/elective/replacement/lab), which describes what a course *is* rather than who
may take it.

**Published** — a term's schedule has been frozen and released. Published sessions
are immovable.

**Reservation** — a provisional graduate session placed during phase 1 to hold
space, standing in for a course not yet finalised.

## Decisions

Each of these was chosen deliberately; the rationale is recorded because the
reasoning is not recoverable from the code.

| # | Decision | Rationale |
| --- | --- | --- |
| D1 | Grad↔grad and grad↔joint overlap is **hard**; joint↔joint is **allowed** | A graduate student combines a grad course with a joint course, so those must not clash. Two joint courses are largely undergraduate-attended and behave like ordinary electives. |
| D2 | The rule covers **every session** — lecture, exercise, lab | A student attends all sessions of their course; an exercise clash blocks them as surely as a lecture clash. Costs nothing at 3–4 grad courses a term. |
| D3 | Level is **stored when set, derived from the number when not**, defaulting to UG | No migration, old catalog files keep importing, and the course number is immutable after creation (`CourseForm.tsx:49`) so derivation only runs at entry. |
| D4 | Grad courses carry **no cohort**; programs and year become optional | A graduate student is not "ChemE Y2". Their protection comes from the level rule. Joint courses keep their undergraduate cohort. |
| D5 | Everything is scoped by **(academic year, semester)** | The department publishes per semester and must be able to say which year a frozen schedule belongs to. |
| D6 | Availability is **per-term, pre-filled from the same semester last year** | A lecturer's commitments are usually stable but not permanent; editing a global set would silently change the constraints a published term was solved under. |
| D7 | Publishing is an **explicit action**, not implicit | Matches "already set and published". Gives an auditable record and a visible lock. |
| D8 | Published UG/joint sessions **freeze**; grad reservations stay **fluid** | The reservation's job — keeping joint courses out of those hours — is complete once phase 1 ends. Binding it afterwards would fail when this year's course differs in length. |
| D9 | External grad course times come from the **skeleton first, manual fallback** | The imported XLSX is university-wide and already contains every faculty's times. The planner maintains a list of course numbers, not a timetable. |
| D10 | Cadence (annual / biennial) drives **reservations only**; the human finalises in phase 2 | A cadence flag is a promise about the future and goes stale silently. Confining it to the reservation stage means a stale flag costs an unused slot, never a wrong schedule. |
| D11 | Graduate courses get their **own PDF page**, separate from the per-cohort pages | Grad courses carry no cohort (D4) and so appear on no cohort page. A dedicated graduate timetable is the output that makes D4 safe. |

### Rejected alternatives

- **Soft grad rule.** Rejected: the department treats it as inviolable. At 3–4 grad
  courses in a 50-box week there is no feasibility pressure to justify relaxing it.
- **A synthetic `Graduate` program** (D4). Rejected: it would fabricate a cohort and
  drag grad courses into per-cohort machinery that does not describe them.
- **Global availability** (D6). Rejected: mutating it would retroactively change the
  basis of a published term.
- **Per-year catalog copies vs snapshot-only history.** Superseded — the planner
  requires everything per-term, so the catalog is genuinely per-term (D5).

## Rule matrix

|            | grad (0058) | joint (0056) | UG elective |
| ---------- | ----------- | ------------ | ----------- |
| **grad**   | **HARD**    | **HARD**     | soft (existing) |
| **joint**  | **HARD**    | allowed      | soft (existing) |

Level is suggested from the course number, and may always be overridden:

| Prefix | Suggested level | Meaning |
| ------ | --------------- | ------- |
| `0054` | UG | Our department's undergraduate course |
| `0056` | joint | Joint undergraduate/graduate |
| `0058` | grad | Pure graduate |
| other  | UG | Another faculty — override to joint/grad as needed |

## Two-phase workflow

```
PHASE 1  ──────────────────────────────────────────────
  solve: UG + joint courses
       + last year's grad courses as reservations ◌
         (carry the hard rules, so joint courses are
          genuinely pushed out of those hours)
  review, edit
  PUBLISH  → stamped "2026-27 Spring"
            UG/joint sessions  🔒 frozen
            grad reservations  ◌ released

PHASE 2  ──────────────────────────────────────────────  (weeks/months later)
  confirm which grad courses actually run
  append: grad courses only
          prefer their reserved slot, may take any free slot
          hard rules vs grad, joint, and external grad courses
  nothing published moves
```

## Data model

### New: term scoping

```sql
CREATE TABLE terms (
    id        TEXT PRIMARY KEY,   -- "2026-27-spring"
    year      TEXT NOT NULL,      -- "2026-27"
    semester  TEXT NOT NULL,      -- "winter" | "spring"
    created   TEXT NOT NULL,      -- ISO date
    published TEXT                -- ISO timestamp, NULL while in progress
);

-- courses and settings gain a term key
CREATE TABLE courses (
    term_id TEXT NOT NULL,
    number  TEXT NOT NULL,
    data    TEXT NOT NULL,
    PRIMARY KEY (term_id, number)
);

CREATE TABLE settings (
    term_id TEXT NOT NULL,        -- '' for global settings
    key     TEXT NOT NULL,
    value   TEXT NOT NULL,
    PRIMARY KEY (term_id, key)
);
```

| Per-term | Global (`term_id = ''`) |
| --- | --- |
| courses, availability, calendar, offered_rows, skeleton_course_numbers, courses_of_interest, last_schedule, published_schedule | people (faculty registry), saves_dir, current_term |

Room inventory stays hardcoded (`domain.py:101`) and is global by construction.

### New: `Course` fields

```python
level: CourseLevel | None = None   # None -> derive from number, default UG
cadence: Cadence = Cadence.ANNUAL  # annual | biennial
provisional: bool = False          # a rolled-over grad course, not yet confirmed
```

`programs` and `year` become optional — validated as required only when
`level != grad`.

### New: `Session` and `FixedEvent` fields

`Session.level` is propagated from its course, exactly as `role` already is
(`catalog.py` `common`). `FixedEvent.level` carries the same for external courses,
so a biology graduate course can block grad placement without owning a cohort.

### Migration

The store opens, finds the old single-term schema, and:

1. Asks the planner to name the current data's term (defaulting to a guess from
   the semester calendar's start date, if set).
2. Creates that term, moves every course and setting into it.
3. Moves `people` and `saves_dir` to global.

Irreversible in-place, so it **takes a timestamped backup of `schedy.sqlite`
first** and reports where it went. Saved schedule JSON files are untouched; they
already snapshot their own catalog.

## Constraint implementation

### The `elif` trap — read before implementing

`evaluator.py:144-168` checks session pairs in a single `if/elif` chain:

```python
if ae and be:                     # elective vs elective   -> SOFT
elif (ae or be) and shared_cohorts:  # elective vs core    -> SOFT
elif shared_cohorts and ...:      # cohort double-booked   -> HARD
```

Graduate courses will almost always carry `role=elective`. If the grad rule is
implemented by giving grad courses a shared synthetic cohort, the **first branch
wins** and the result is a soft warning, not a hard block — silently wrong.

The grad rule must therefore be an **independent check**, evaluated regardless of
which branch of the elective chain fires:

```python
# new, unconditional
if _grad_clash(sa, sb):           # grad↔grad or grad↔joint
    out.append(Violation("grad_overlap", HARD, ...))
```

Mirrored in `model_builder.py` as a hard no-overlap constraint over the set of
grad + joint sessions, and extended to `FixedEvent`s carrying `level in (grad, joint)`.

### Room pinning gap — read before implementing

`fixed_day`/`fixed_box` pin a session's **time but not its room** — `domain.py:164`
says so explicitly: *"Room is still solver-chosen."*

Phase 2 therefore cannot freeze a published schedule with the existing mechanism
alone: the solver would honour every published time but remain free to shuffle
rooms, changing the published timetable. A `fixed_room` (or an equivalent
whole-placement pin) is required, and is a prerequisite for phase 2.

## API surface

| Method | Route | Purpose |
| --- | --- | --- |
| GET | `/terms` | List terms with status |
| POST | `/terms` | Create a term, optionally rolling over from another |
| GET/PUT | `/terms/current` | Read/switch the active term |
| PUT | `/terms/{id}` | Re-label a term, keeping its data — how a migration's guessed name is confirmed or corrected |
| POST | `/terms/{id}/publish` | Freeze UG+joint placements, stamp published |
| DELETE | `/terms/{id}/publish` | Un-publish (explicit, confirmed — see risks) |
| GET | `/terms/{id}/rollover-preview` | Grad courses from the previous same semester, with last-run and cadence |
| POST | `/solve` | Phase 1 — unchanged, scoped to the current term |
| POST | `/solve/grad` | Phase 2 — pin published sessions, place grad only |
| GET | `/levels/suggest?number=` | Level suggested from a course number |

Every existing route becomes term-scoped implicitly via the current term; no route
gains a term parameter except those above.

## UI changes

| Tab | Change |
| --- | --- |
| **Header** | Term selector — `2026-27 Spring ▾` — with status badge (in progress / 🔒 published). Switching terms swaps the whole working set. |
| **Catalog** | Level field with the suggested value pre-filled and a note showing it came from the number. Programs/year hidden or optional when level is grad. Cadence selector on grad courses. Level shown as a tag in the list. |
| **Schedule** | `🔒 Publish` action beside Save. Published sessions render locked and refuse drags. Grad reservations render distinctly (new legend entry alongside the existing role colours, `App.tsx:369`). `+ Add graduate courses` starts phase 2 once published. |
| **Availability** | Unchanged in behaviour; its data is now term-scoped and pre-filled on rollover. |
| **Calendar / Import / Checklist** | Unchanged in behaviour; term-scoped data. |
| **Schedules** | Saves list gains the term each save belongs to. |
| **New: Rollover** | Shown when creating a term. Lists known grad courses with when each last ran and its cadence; due ones pre-ticked. Ticking creates provisional grad courses for reservations. |

All new strings bilingual Hebrew (RTL) / English, per existing convention.

## Test plan

**Level derivation** — each prefix maps correctly; unknown prefixes default to UG;
a stored level always beats the derived one; a course stored before the field
existed reads as UG.

**Clash rules** — grad↔grad hard; grad↔joint hard; joint↔joint produces no hard
violation; **grad↔grad where both are `role=elective` is still hard** (the `elif`
trap, as a named regression test); grad↔UG-elective remains soft; a grad
`FixedEvent` from another faculty blocks a grad session.

**Cohort-less grad** — a grad course with no programs expands without error,
produces sessions, and triggers no `cohort_double_booked` against anything.

**Publish / freeze** — publishing stamps the term; a published session cannot be
moved by phase 2, **including its room**; un-publishing requires explicit confirm.

**Phase 2** — grad courses prefer their reserved slot; take another free slot when
the reservation no longer fits; a grad course that cannot be placed is reported
unplaced with the published schedule intact.

**Term scoping** — two terms hold independent catalogs; switching terms swaps the
working set; global settings (people) are shared; a save records its term.

**Migration** — an old single-term database migrates with every course and setting
preserved; a backup file is produced; migration is idempotent.

**Rollover** — grad courses come from the same semester one year back; a biennial
course that ran two years ago is listed and pre-ticked; an annual course that ran
last year is pre-ticked; availability is pre-filled and the source term unchanged.

## Risks

**Migration against live data.** The planner already has a production database (15
courses at time of writing) and saved schedules. The migration is the single most
dangerous change here. Mitigations: timestamped backup before touching anything,
idempotent, and verified against a copy of the real database before release.

**Scope.** The per-term re-architecture touches the store schema, every API route
and every panel. It is far larger than the graduate rule that motivated it, and
carries most of the risk. Sequencing it first and alone was recommended and
declined in favour of this document; it remains the recommendation for the build.

**Grad courses are invisible in cohort exports.** PDF timetables render one page
per cohort, so a cohort-less grad course appears on no page. Resolved by D11: a
dedicated graduate PDF page. Must ship with phase 2, not after it.

**Un-publishing.** If a published schedule must be corrected, phase 2 work and the
freeze interact in ways not yet designed. Currently specified as an explicit
confirmed action; the consequences for already-appended grad courses are undefined.

**Room pinning** is a prerequisite, not a detail (see above). Phase 2 is unsound
without it.

## Open questions

1. What happens to appended grad courses if a published term is un-published and
   re-solved?
2. Should phase 1 warn when reservations consume an unreasonable share of the week?
3. Do joint (0056) courses ever serve more than one undergraduate year?

## Recommended build sequence

1. **Term model + migration**, verified against a copy of the production database.
2. **`fixed_room`** — prerequisite for freezing.
3. **Level field + prefix suggestion**, back-compatible.
4. **Clash rules** — independent check, with the `elif`-trap regression test.
5. **Publish / freeze.**
6. **Phase 2 append + reservations**, including the graduate PDF page (D11).
7. **Rollover + cadence.**

Steps 3 and 4 deliver standalone value on the current single-term model and could
ship first if the term model proves slow, at the cost of some rework where they meet.
