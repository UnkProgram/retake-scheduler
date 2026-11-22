"""Импорт исходных данных из CSV-файлов.

Форматы файлов (разделитель «,» или «;», кодировка UTF-8, первая строка — заголовок).
Списки внутри ячейки разделяются символом «|».

- rooms:    name, capacity
- slots:    date, start, end                (дата ГГГГ-ММ-ДД, время ЧЧ:ММ)
- teachers: name, available                 («*» — все слоты; «ГГГГ-ММ-ДД» — весь день;
                                              «ГГГГ-ММ-ДД ЧЧ:ММ» — один слот)
- students: name, group                     (необязательный файл)
- exams:    subject, teachers, students     (имена через «|»)
"""
from __future__ import annotations

import csv
import io
from dataclasses import dataclass, field
from datetime import datetime

from scheduler.core.models import Exam, Problem, Room, Slot, Student, Teacher

LIST_SEP = "|"


@dataclass(frozen=True)
class ImportIssue:
    """Ошибка в строке входного файла."""

    file: str
    line: int
    message: str

    def __str__(self) -> str:
        where = f"{self.file}, строка {self.line}" if self.line else self.file
        return f"{where}: {self.message}"


@dataclass
class ImportResult:
    """Результат импорта: данные (если ошибок нет) и список ошибок."""

    problem: Problem | None = None
    errors: list[ImportIssue] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors


def _parse(text: str) -> tuple[list[str], list[tuple[int, dict[str, str]]]]:
    """Разбирает CSV: возвращает заголовки и список (номер строки, значения по заголовкам)."""
    text = text.lstrip("\ufeff")
    first = text.splitlines()[0] if text.strip() else ""
    delimiter = ";" if first.count(";") > first.count(",") else ","
    reader = csv.DictReader(io.StringIO(text), delimiter=delimiter)
    header = [(h or "").strip().lower() for h in (reader.fieldnames or [])]
    reader.fieldnames = header
    rows = []
    for number, row in enumerate(reader, start=2):
        values = {k: (v or "").strip() for k, v in row.items() if k}
        if any(values.values()):
            rows.append((number, values))
    return header, rows


def _rows(text: str) -> list[tuple[int, dict[str, str]]]:
    return _parse(text)[1]


def _split(value: str) -> list[str]:
    return [part.strip() for part in value.split(LIST_SEP) if part.strip()]


def _check_columns(file: str, text: str, required: list[str], errors: list[ImportIssue]) -> bool:
    """Проверяет, что файл не пуст и содержит нужные столбцы и хотя бы одну строку данных."""
    if not text.strip():
        errors.append(ImportIssue(file, 0, "файл пуст"))
        return False
    header, rows = _parse(text)
    missing = [c for c in required if c not in header]
    if missing:
        errors.append(ImportIssue(file, 1, "нет столбцов: " + ", ".join(missing)))
        return False
    if not rows:
        errors.append(ImportIssue(file, 0, "в файле нет данных"))
        return False
    return True


def _valid_date(value: str) -> bool:
    try:
        datetime.strptime(value, "%Y-%m-%d")
    except ValueError:
        return False
    return True


def _valid_time(value: str) -> bool:
    try:
        datetime.strptime(value, "%H:%M")
    except ValueError:
        return False
    return True


def parse_rooms(text: str, errors: list[ImportIssue]) -> list[Room]:
    rooms: list[Room] = []
    if not _check_columns("rooms", text, ["name", "capacity"], errors):
        return rooms
    seen: set[str] = set()
    for line, row in _rows(text):
        name = row.get("name", "")
        if not name:
            errors.append(ImportIssue("rooms", line, "не указано название аудитории"))
            continue
        if name in seen:
            errors.append(ImportIssue("rooms", line, f"аудитория «{name}» повторяется"))
            continue
        if not row.get("capacity", "").isdigit() or int(row["capacity"]) < 1:
            errors.append(ImportIssue("rooms", line, "вместимость должна быть целым числом ≥ 1"))
            continue
        seen.add(name)
        rooms.append(Room(len(rooms) + 1, name, int(row["capacity"])))
    return rooms


def parse_slots(text: str, errors: list[ImportIssue]) -> list[Slot]:
    slots: list[Slot] = []
    if not _check_columns("slots", text, ["date", "start", "end"], errors):
        return slots
    seen: set[tuple[str, str]] = set()
    for line, row in _rows(text):
        date, start, end = row.get("date", ""), row.get("start", ""), row.get("end", "")
        if not _valid_date(date):
            errors.append(ImportIssue("slots", line, f"неверная дата «{date}», нужен ГГГГ-ММ-ДД"))
        elif not (_valid_time(start) and _valid_time(end)):
            errors.append(ImportIssue("slots", line, "неверное время, нужен формат ЧЧ:ММ"))
        elif end <= start:
            errors.append(ImportIssue("slots", line, "время окончания должно быть позже начала"))
        elif (date, start) in seen:
            errors.append(ImportIssue("slots", line, f"слот {date} {start} повторяется"))
        else:
            seen.add((date, start))
            slots.append(Slot(len(slots) + 1, date, start, end))
    return slots


def parse_teachers(text: str, slots: list[Slot], errors: list[ImportIssue]) -> list[Teacher]:
    teachers: list[Teacher] = []
    if not _check_columns("teachers", text, ["name", "available"], errors):
        return teachers
    by_key = {s.key: s.id for s in slots}
    seen: set[str] = set()
    for line, row in _rows(text):
        name = row.get("name", "")
        if not name:
            errors.append(ImportIssue("teachers", line, "не указано имя преподавателя"))
            continue
        if name in seen:
            errors.append(ImportIssue("teachers", line, f"преподаватель «{name}» повторяется"))
            continue
        available: set[int] = set()
        bad = False
        for item in _split(row.get("available", "")):
            if item == "*":
                available |= {s.id for s in slots}
            elif item in by_key:
                available.add(by_key[item])
            elif _valid_date(item) and any(s.date == item for s in slots):
                available |= {s.id for s in slots if s.date == item}
            else:
                errors.append(ImportIssue("teachers", line, f"неизвестный слот или дата «{item}»"))
                bad = True
        if not bad:
            seen.add(name)
            teachers.append(Teacher(len(teachers) + 1, name, frozenset(available)))
    return teachers


def parse_students(text: str | None, errors: list[ImportIssue]) -> list[Student]:
    students: list[Student] = []
    if not text or not text.strip():
        return students
    if not _check_columns("students", text, ["name"], errors):
        return students
    seen: set[str] = set()
    for line, row in _rows(text):
        name = row.get("name", "")
        if not name:
            errors.append(ImportIssue("students", line, "не указано имя студента"))
        elif name in seen:
            errors.append(ImportIssue("students", line, f"студент «{name}» повторяется"))
        else:
            seen.add(name)
            students.append(Student(len(students) + 1, name, row.get("group", "")))
    return students


def parse_exams(
    text: str,
    teachers: list[Teacher],
    students: list[Student],
    errors: list[ImportIssue],
) -> list[Exam]:
    exams: list[Exam] = []
    if not _check_columns("exams", text, ["subject", "teachers", "students"], errors):
        return exams
    teacher_ids = {t.name: t.id for t in teachers}
    student_ids = {s.name: s.id for s in students}
    for line, row in _rows(text):
        subject = row.get("subject", "")
        names = _split(row.get("teachers", ""))
        learners = _split(row.get("students", ""))
        problems = []
        if not subject:
            problems.append("не указан предмет")
        if not names:
            problems.append("не указан ни один преподаватель")
        unknown = [n for n in names if n not in teacher_ids]
        if unknown:
            problems.append("неизвестные преподаватели: " + ", ".join(unknown))
        if not learners:
            problems.append("не указан ни один студент")
        if len(set(learners)) != len(learners):
            problems.append("студент указан несколько раз")
        if len(set(names)) != len(names):
            problems.append("преподаватель указан несколько раз")
        if problems:
            errors.append(ImportIssue("exams", line, "; ".join(problems)))
            continue
        for learner in learners:
            if learner not in student_ids:
                student = Student(len(students) + 1, learner, "")
                students.append(student)
                student_ids[learner] = student.id
        exams.append(Exam(
            len(exams) + 1,
            subject,
            tuple(teacher_ids[n] for n in names),
            tuple(student_ids[s] for s in learners),
        ))
    return exams


def import_problem(
    rooms: str, slots: str, teachers: str, exams: str, students: str | None = None
) -> ImportResult:
    """Разбирает пять CSV-текстов и собирает задачу. При ошибках problem равен None."""
    errors: list[ImportIssue] = []
    room_list = parse_rooms(rooms, errors)
    slot_list = parse_slots(slots, errors)
    teacher_list = parse_teachers(teachers, slot_list, errors)
    student_list = parse_students(students, errors)
    exam_list = parse_exams(exams, teacher_list, student_list, errors)
    if errors:
        return ImportResult(None, errors)
    return ImportResult(Problem(slot_list, room_list, teacher_list, student_list, exam_list), [])
