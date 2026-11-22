"""Тесты импорта CSV."""
from scheduler.importers.csv_importer import import_problem

ROOMS = "name,capacity\nА-101,30\nБ-201,4\n"
SLOTS = "date,start,end\n2026-12-14,09:00,10:00\n2026-12-14,10:00,11:00\n2026-12-15,09:00,10:00\n"
TEACHERS = (
    "name,available\nИванов,*\nПетров,2026-12-14\n"
    "Сидоров,2026-12-15 09:00|2026-12-14 10:00\n"
)
EXAMS = "subject,teachers,students\nБД,Иванов|Петров,Аня|Борис\nОС,Сидоров,Аня\n"


def run(**overrides):
    files = {"rooms": ROOMS, "slots": SLOTS, "teachers": TEACHERS, "exams": EXAMS}
    files.update(overrides)
    return import_problem(**files)


def messages(result):
    return [str(e) for e in result.errors]


def test_valid_files_are_imported():
    result = run()
    assert result.ok
    problem = result.problem
    assert len(problem.rooms) == 2 and len(problem.slots) == 3 and len(problem.exams) == 2


def test_availability_formats():
    teachers = {t.name: t.available for t in run().problem.teachers}
    assert teachers["Иванов"] == frozenset({1, 2, 3})
    assert teachers["Петров"] == frozenset({1, 2})
    assert teachers["Сидоров"] == frozenset({2, 3})


def test_students_are_created_from_exams():
    names = [s.name for s in run().problem.students]
    assert names == ["Аня", "Борис"]


def test_students_file_keeps_groups():
    result = run(students="name,group\nАня,ИВТ-31\n")
    groups = {s.name: s.group for s in result.problem.students}
    assert groups == {"Аня": "ИВТ-31", "Борис": ""}


def test_semicolon_delimiter_and_bom():
    result = run(rooms="\ufeffname;capacity\nА-101;30\n")
    assert result.ok and result.problem.rooms[0].capacity == 30


def test_bad_capacity_is_reported_with_line():
    result = run(rooms="name,capacity\nА-101,много\n")
    assert not result.ok
    assert "rooms, строка 2" in messages(result)[0]


def test_bad_date_is_reported():
    result = run(slots="date,start,end\n14.12.2026,09:00,10:00\n")
    assert any("неверная дата" in m for m in messages(result))


def test_end_before_start_is_reported():
    result = run(slots="date,start,end\n2026-12-14,10:00,09:00\n")
    assert any("позже начала" in m for m in messages(result))


def test_unknown_teacher_in_exam_is_reported():
    result = run(exams="subject,teachers,students\nБД,Неизвестный,Аня\n")
    assert any("неизвестные преподаватели" in m for m in messages(result))


def test_unknown_slot_in_availability_is_reported():
    result = run(teachers="name,available\nИванов,2030-01-01\n")
    assert any("неизвестный слот" in m for m in messages(result))


def test_missing_column_is_reported():
    result = run(rooms="name\nА-101\n")
    assert any("нет столбцов" in m for m in messages(result))


def test_empty_file_is_reported():
    result = run(rooms="")
    assert any("файл пуст" in m for m in messages(result))


def test_problem_is_none_when_errors_exist():
    assert run(rooms="name,capacity\nА,0\n").problem is None
