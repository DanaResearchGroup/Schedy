"""A realistic sample department catalog for demos and first-run onboarding.

One illustrative Spring semester for the Chemical Engineering department: core
courses for both programs across years 1-4, a cross-day lab, a lab-only course,
electives that should not collide, a Zoom-only course, a computer-farm course,
and an externally-fixed course (given by another department) that the solver must
schedule around. Numbers/names are plausible but illustrative, not authoritative.

Kept deliberately small so a fresh user can hit Solve and see a full, legible
weekly schedule in seconds.
"""

from __future__ import annotations

from .catalog import Course
from .domain import CourseRole, Program

CHEME = Program.CHEME
BIO = Program.BIOCHEME

# Day indices: Sun=0 Mon=1 Tue=2 Wed=3 Thu=4. Minutes are minute-of-day.
_8_30 = 8 * 60 + 30


def sample_courses() -> list[Course]:
    """The demo catalog: department courses + one external wall."""
    return [
        # ---- Year 1: shared core (both programs) ----------------------- #
        Course(
            number="01040031", name_he="חשבון דיפרנציאלי ואינטגרלי 1",
            name_en="Calculus 1 (external)", programs=[CHEME, BIO], year=1,
            role=CourseRole.CORE, expected_enrollment=120,
            # Given by the Math department at a fixed slot — an immovable wall.
            is_external=True, ext_day=1, ext_start_min=_8_30,
            ext_end_min=_8_30 + 2 * 60,
        ),
        Course(
            number="01250300", name_he="כימיה כללית", name_en="General Chemistry",
            programs=[CHEME, BIO], year=1, role=CourseRole.CORE,
            lecture_boxes=2, num_exercise_groups=2, exercise_boxes=1,
            expected_enrollment=110, lecturer_ids=["prof_levi"],
            ta_ids=["ta_adi", "ta_noa"],
        ),

        # ---- Year 2 ---------------------------------------------------- #
        Course(
            number="00540315", name_he="תרמודינמיקה א׳", name_en="Thermodynamics A",
            programs=[CHEME], year=2, role=CourseRole.CORE,
            lecture_boxes=2, num_exercise_groups=2, exercise_boxes=1,
            # Lab offered on two days so groups colliding with single-program
            # cores still have an attainable alternative (see PRD example).
            lab_boxes=2, lab_days=[0, 3], expected_enrollment=70,
            lecturer_ids=["prof_bar"], ta_ids=["ta_hedva", "ta_yossi"],
        ),
        Course(
            number="00540316", name_he="מכניקת זורמים", name_en="Fluid Mechanics",
            programs=[CHEME, BIO], year=2, role=CourseRole.CORE,
            lecture_boxes=3, num_exercise_groups=2, exercise_boxes=1,
            expected_enrollment=95, lecturer_ids=["prof_cohen"],
            ta_ids=["ta_dan", "ta_maya"],
        ),
        Course(
            number="01250420", name_he="כימיה אורגנית", name_en="Organic Chemistry",
            programs=[CHEME, BIO], year=2, role=CourseRole.CORE,
            lecture_boxes=2, num_exercise_groups=1, exercise_boxes=2,
            expected_enrollment=90, lecturer_ids=["dr_shapiro"], ta_ids=["ta_lior"],
        ),

        # ---- Year 3 ---------------------------------------------------- #
        Course(
            number="00540322", name_he="תהליכי מעבר חום וחומר",
            name_en="Heat & Mass Transfer", programs=[CHEME, BIO], year=3,
            role=CourseRole.CORE, lecture_boxes=3, num_exercise_groups=2,
            exercise_boxes=1, expected_enrollment=80,
            lecturer_ids=["prof_bar"], ta_ids=["ta_yossi", "ta_dan"],
        ),
        Course(
            number="00540323", name_he="הנדסת ריאקטורים", name_en="Reaction Engineering",
            programs=[CHEME], year=3, role=CourseRole.CORE,
            lecture_boxes=2, num_exercise_groups=2, exercise_boxes=1,
            expected_enrollment=55, lecturer_ids=["prof_katz"], ta_ids=["ta_maya"],
        ),
        Course(
            number="00540325", name_he="בקרת תהליכים", name_en="Process Control",
            programs=[CHEME], year=3, role=CourseRole.CORE,
            lecture_boxes=2, num_exercise_groups=1, exercise_boxes=2,
            # Tutorials run in the simulation computer farm.
            needs_computer_farm=True, expected_enrollment=20,
            lecturer_ids=["dr_friedman"], ta_ids=["ta_omer"],
        ),
        Course(
            number="00540390", name_he="מעבדה בהנדסה כימית 2",
            name_en="ChemE Lab 2", programs=[CHEME], year=3, role=CourseRole.LAB,
            # Lab-only course: no lecture, no exercises.
            lab_boxes=4, lab_days=[1, 2], expected_enrollment=40,
            ta_ids=["ta_hedva", "ta_lior"],
        ),
        Course(
            number="00540331", name_he="מבוא לביוכימיה ואנזימולוגיה",
            name_en="Intro to Biochemistry & Enzymology",
            programs=[CHEME], year=3, role=CourseRole.CORE,
            lecture_boxes=2, num_exercise_groups=1, exercise_boxes=1,
            expected_enrollment=60, lecturer_ids=["prof_green"], ta_ids=["ta_noa"],
        ),
        Course(
            number="01360350", name_he="גנטיקה מולקולרית",
            name_en="Molecular Genetics", programs=[BIO], year=3,
            role=CourseRole.CORE, lecture_boxes=2, num_exercise_groups=1,
            exercise_boxes=1, expected_enrollment=45,
            lecturer_ids=["prof_rosen"], ta_ids=["ta_adi"],
        ),

        # ---- Year 4: design + electives -------------------------------- #
        Course(
            number="00540401", name_he="תכן תהליכים ומפעלים",
            name_en="Process & Plant Design", programs=[CHEME], year=4,
            role=CourseRole.CORE, lecture_boxes=3, num_exercise_groups=1,
            exercise_boxes=2, expected_enrollment=50,
            lecturer_ids=["prof_katz", "dr_friedman"], ta_ids=["ta_omer"],
        ),
        Course(
            number="00540470", name_he="ננו-הנדסה בהשראת הטבע",
            name_en="Nano-Engineering Inspired by Nature",
            programs=[CHEME, BIO], year=4, role=CourseRole.ELECTIVE,
            lecture_boxes=2, expected_enrollment=35,
            lecturer_ids=["prof_green"],
        ),
        Course(
            number="00540471", name_he="מיקרוסקופיית אלקטרונים",
            name_en="Electron Microscopy", programs=[CHEME, BIO], year=4,
            role=CourseRole.ELECTIVE, lecture_boxes=2, expected_enrollment=30,
            lecturer_ids=["dr_shapiro"],
        ),
        Course(
            number="00540480", name_he="מדעי הפולימרים (מקוון)",
            name_en="Polymer Science (online)", programs=[CHEME, BIO], year=4,
            role=CourseRole.ELECTIVE, lecture_boxes=2, is_remote=True,
            expected_enrollment=40, lecturer_ids=["prof_rosen"],
        ),
    ]
