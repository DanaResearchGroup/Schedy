name: schedy

## Structure:

Two Programs:
- Chemical Engineering (ChemE)
- Biochemical Engineering (BioChemE)
- Chemical Engineering Chemistry


## Course Types
- Core courses for ChemE only (yellow)
- Core courses for BioChemE only (green)
- Core courses for ChemE & BioChemE (light blue)
- Electives for ChemE & BioChemE (orange)
- Replacements courses (courses that students are allowed to expand instead of their other core courses) for ChemE & BioChemE (blue)


## Instructions for scheduling the academic courses throughout the year:

What is a Course?
A Course object has a University course number (e.g., 00540319)
A Course has a Lecturer (or more)
A Course may or may not have exercises with one or more TAs
A Course may or may not have a lab with one or more TAs
A course can be core for all our students, just for ChemE, or just for BioChemE. Or it could be an elective.

There are also Courses that are only lab (like "ChemE lab 2") with no Lecture and no exercises. This would be defined as a "Lab" Course.


Each Lecture and Exercise has a Classroom assigned to it. In our Department we have Hall 1 (210 max occupants), classroom 2 (a computer farm, for 22 students), Classroom 3 (50), Classroom 4 (50) , Classroom 4 (50), Hall 6 (120)


We are planning the teaching schedule for the entire Department. This means that there are at each given moments students in their 1st year, 2nd year, 3rd year, and 4th year.

We will run the software each time for a single semester a year (1st semester called "Winter", and 2nd semester called "Spring").

We need to make sure that different courses for the different years don't collide in terms of physical Classrooms and Halls. 

Courses for the same audience and same year cannot collide.
But course that are meant for ChemE only can be given at the same time as courses given for BioChemE. But not in the same room of course.


initially, you'll get a schedule from thr University (Technion) with a bare schedule (called "skeleton" or "Shildit" in Hebrew), see for example 30.4.26.XLSX in ~/Projects/Schedy/)

extract only the relevant courses (and the specific TA exercises from them) that are relevant for our Departmen. The user will define at the outset these courses.

we need to first run tests on the skeleton. If TA sessions of specific groups (e.g. HEDVA Exercise 13 is missing) then alert the user. thee user will provide at the outset the specific exercises to look for

Each Wed. at 12:30-14:30 there are no courses (free time for students - "Wed. Afternoon")
Each Monday at 13:30-14:30 there's a departmental Seminar, don't schedule any lectures/exercises /labs in this window as well

We will get each semester the constraints of the Lecturers (e.g., Lecturer X can't teach on Wednesdays)
Each course is assign a Lecturer (or two) and a TA (or more).

We have constrains of core courses determined by other departments, we need to schedule "around" them

For example, the Thermodynamics lab has two days a week for different student groups. Make sure that if it collides with **Core** courses of ChemE only or of BioChemE only, then each student can still take the lab on one of the week days. For example: Thermodynamics A has a lab given on Sunday and Wednesday. On Sunday at the same time there's a Molecular Genetics course for BioChemE students only (core). On Wednesday at the same time there's a Intro to Biochemistry and Enzymology which is a core course for ChemE. This works out well, since BioChemE students can take the Thermodynamics A lab on Wed. which ChemE students can take it on Sun.


Elective courses:
The rational is that electives won't be given at the same time, since they are open to all years (usually for students from 3rd, and 4th years)
For example: We don't want Nano-Engineering Inspired  By Mature to be scheduled at the same time as Electron Microscopy (both are electives), since then students won't be able to take both in the same semester.
Also, we should avoid scheduling electives at the same time as core courses.

Electives for BioChemE students only are mostly offered by the Biology Department (not controlled by us). We should avoid giving our own electives at the same time, as much as possible.


can't have both TA sessions of the same course given at the same time.

electives from other departments (Biology, Chemistry, etc.): recommend to students at which semester they should be taken them, make sure they don't overlap with core courses

Can find different TA session times of the same course for ChemE and for BioChemE students according to the different core and electives they have

Courses that are only given remotely (Zoom) should not be in the middle of the day, put the meetings in the morning/late afternoon







