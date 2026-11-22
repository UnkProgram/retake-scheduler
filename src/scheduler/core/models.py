"""Модели предметной области планировщика пересдач и защит."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Slot:
    """Временной слот, в который можно провести пересдачу или защиту."""

    id: int
    date: str  # формат ГГГГ-ММ-ДД
    start: str  # формат ЧЧ:ММ
    end: str  # формат ЧЧ:ММ

    @property
    def key(self) -> str:
        """Человекочитаемый ключ слота, например «2026-12-01 09:00»."""
        return f"{self.date} {self.start}"


@dataclass(frozen=True)
class Room:
    """Аудитория с ограниченной вместимостью."""

    id: int
    name: str
    capacity: int


@dataclass(frozen=True)
class Teacher:
    """Преподаватель и множество слотов, в которые он свободен."""

    id: int
    name: str
    available: frozenset[int] = frozenset()


@dataclass(frozen=True)
class Student:
    """Студент, участвующий в пересдаче или защите."""

    id: int
    name: str
    group: str = ""


@dataclass(frozen=True)
class Exam:
    """Одна пересдача или защита: предмет, комиссия и студенты."""

    id: int
    subject: str
    teacher_ids: tuple[int, ...]
    student_ids: tuple[int, ...]


@dataclass(frozen=True)
class Assignment:
    """Назначение пересдачи на слот и аудиторию."""

    exam_id: int
    slot_id: int
    room_id: int


@dataclass
class Problem:
    """Полные входные данные для составления расписания."""

    slots: list[Slot] = field(default_factory=list)
    rooms: list[Room] = field(default_factory=list)
    teachers: list[Teacher] = field(default_factory=list)
    students: list[Student] = field(default_factory=list)
    exams: list[Exam] = field(default_factory=list)

    def slots_by_id(self) -> dict[int, Slot]:
        return {s.id: s for s in self.slots}

    def rooms_by_id(self) -> dict[int, Room]:
        return {r.id: r for r in self.rooms}

    def teachers_by_id(self) -> dict[int, Teacher]:
        return {t.id: t for t in self.teachers}

    def students_by_id(self) -> dict[int, Student]:
        return {s.id: s for s in self.students}

    def exams_by_id(self) -> dict[int, Exam]:
        return {e.id: e for e in self.exams}


@dataclass
class Result:
    """Результат работы алгоритма составления расписания."""

    assignments: dict[int, Assignment] = field(default_factory=dict)
    unscheduled: dict[int, str] = field(default_factory=dict)  # id пересдачи -> причина
    nodes: int = 0  # число шагов поиска
    complete: bool = False  # все ли пересдачи удалось разместить
