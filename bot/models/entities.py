from __future__ import annotations

from datetime import date, datetime, time
from enum import Enum

from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    Time,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from bot.utils.db import Base


class Role(str, Enum):
    STUDENT = "student"
    STAROSTA = "starosta"
    ADMIN = "admin"


class SubjectKind(str, Enum):
    LAB = "lab"
    PRACTICE = "practice"


class ScheduleWeekType(str, Enum):
    LOWER = "lower"
    UPPER = "upper"


class ScheduleLessonType(str, Enum):
    LAB = "lab"
    PRACTICE = "practice"
    LECTURE = "lecture"
    OTHER = "other"


class Faculty(Base):
    __tablename__ = "faculties"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)

    groups: Mapped[list[Group]] = relationship("Group", back_populates="faculty")


class Group(Base):
    __tablename__ = "groups"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    faculty_id: Mapped[int] = mapped_column(ForeignKey("faculties.id"), nullable=False)
    roster_loaded: Mapped[bool] = mapped_column(Boolean, default=False)

    faculty: Mapped[Faculty] = relationship("Faculty", back_populates="groups")
    students: Mapped[list[Student]] = relationship("Student", back_populates="group")
    group_subjects: Mapped[list[GroupSubject]] = relationship("GroupSubject", back_populates="group")
    schedule_templates: Mapped[list[ScheduleTemplate]] = relationship("ScheduleTemplate", back_populates="group")
    schedule_bindings: Mapped[list[ScheduleBinding]] = relationship("ScheduleBinding", back_populates="group")


class Student(Base):
    __tablename__ = "students"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    last_name: Mapped[str] = mapped_column(String(64), nullable=False)
    first_name: Mapped[str] = mapped_column(String(64), nullable=False)
    middle_name: Mapped[str | None] = mapped_column(String(64))
    group_id: Mapped[int] = mapped_column(ForeignKey("groups.id"), nullable=False)
    is_inactive: Mapped[bool] = mapped_column(Boolean, default=False)

    group: Mapped[Group] = relationship("Group", back_populates="students")
    submissions: Mapped[list[Submission]] = relationship("Submission", back_populates="student")
    user: Mapped[User | None] = relationship("User", back_populates="student", uselist=False)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tg_id: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=False)
    username: Mapped[str | None] = mapped_column(String(64))
    role: Mapped[str] = mapped_column(String(16), default=Role.STUDENT.value)
    student_id: Mapped[int | None] = mapped_column(ForeignKey("students.id"))
    admin_group_id: Mapped[int | None] = mapped_column(ForeignKey("groups.id"))
    is_admin_mode: Mapped[bool] = mapped_column(Boolean, default=False)

    student: Mapped[Student | None] = relationship("Student", back_populates="user")
    admin_group: Mapped[Group | None] = relationship("Group")


class Subject(Base):
    __tablename__ = "subjects"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    kind: Mapped[str] = mapped_column(String(16), default=SubjectKind.LAB.value)

    group_subjects: Mapped[list[GroupSubject]] = relationship("GroupSubject", back_populates="subject")


class GroupSubject(Base):
    __tablename__ = "group_subjects"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    group_id: Mapped[int] = mapped_column(ForeignKey("groups.id"), nullable=False)
    subject_id: Mapped[int] = mapped_column(ForeignKey("subjects.id"), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    group: Mapped[Group] = relationship("Group", back_populates="group_subjects")
    subject: Mapped[Subject] = relationship("Subject", back_populates="group_subjects")
    works: Mapped[list[SubjectWork]] = relationship("SubjectWork", back_populates="group_subject")
    submissions: Mapped[list[Submission]] = relationship("Submission", back_populates="group_subject")
    schedule_bindings: Mapped[list[ScheduleBinding]] = relationship("ScheduleBinding", back_populates="group_subject")

    __table_args__ = (UniqueConstraint("group_id", "subject_id", name="uq_group_subject"),)


class SubjectWork(Base):
    __tablename__ = "subject_works"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    group_subject_id: Mapped[int] = mapped_column(ForeignKey("group_subjects.id"), nullable=False)
    number: Mapped[int] = mapped_column(Integer, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    group_subject: Mapped[GroupSubject] = relationship("GroupSubject", back_populates="works")

    __table_args__ = (UniqueConstraint("group_subject_id", "number", name="uq_work_number"),)


class Submission(Base):
    __tablename__ = "submissions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id"), nullable=False)
    group_subject_id: Mapped[int] = mapped_column(ForeignKey("group_subjects.id"), nullable=False)
    work_number: Mapped[int] = mapped_column(Integer, nullable=False)
    score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    submitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

    student: Mapped[Student] = relationship("Student", back_populates="submissions")
    group_subject: Mapped[GroupSubject] = relationship("GroupSubject", back_populates="submissions")

    __table_args__ = (UniqueConstraint("student_id", "group_subject_id", "work_number", name="uq_submission"),)


class ScheduleTemplate(Base):
    __tablename__ = "schedule_templates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    group_id: Mapped[int] = mapped_column(ForeignKey("groups.id"), nullable=False)
    week_type: Mapped[str] = mapped_column(String(16), nullable=False)
    week_start: Mapped[date] = mapped_column(Date, nullable=False)
    uploaded_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)

    group: Mapped[Group] = relationship("Group", back_populates="schedule_templates")
    entries: Mapped[list[ScheduleEntry]] = relationship(
        "ScheduleEntry",
        back_populates="template",
        cascade="all, delete-orphan",
    )

    __table_args__ = (UniqueConstraint("group_id", "week_type", name="uq_group_schedule_template"),)


class ScheduleEntry(Base):
    __tablename__ = "schedule_entries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    template_id: Mapped[int] = mapped_column(ForeignKey("schedule_templates.id"), nullable=False)
    weekday: Mapped[int] = mapped_column(Integer, nullable=False)
    lesson_date: Mapped[date | None] = mapped_column(Date)
    pair_number: Mapped[int] = mapped_column(Integer, nullable=False)
    time_from: Mapped[time] = mapped_column(Time, nullable=False)
    time_to: Mapped[time] = mapped_column(Time, nullable=False)
    lesson_type: Mapped[str] = mapped_column(String(16), nullable=False)
    discipline: Mapped[str] = mapped_column(String(255), nullable=False)
    discipline_base: Mapped[str] = mapped_column(String(255), nullable=False)
    discipline_key: Mapped[str] = mapped_column(String(255), nullable=False)
    subgroup: Mapped[str | None] = mapped_column(String(64))
    teacher: Mapped[str | None] = mapped_column(String(255))
    room: Mapped[str | None] = mapped_column(String(128))

    template: Mapped[ScheduleTemplate] = relationship("ScheduleTemplate", back_populates="entries")


class ScheduleBinding(Base):
    __tablename__ = "schedule_bindings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    group_id: Mapped[int] = mapped_column(ForeignKey("groups.id"), nullable=False)
    discipline_key: Mapped[str] = mapped_column(String(255), nullable=False)
    discipline_label: Mapped[str] = mapped_column(String(255), nullable=False)
    lesson_type: Mapped[str] = mapped_column(String(16), nullable=False)
    group_subject_id: Mapped[int] = mapped_column(ForeignKey("group_subjects.id"), nullable=False)

    group: Mapped[Group] = relationship("Group", back_populates="schedule_bindings")
    group_subject: Mapped[GroupSubject] = relationship("GroupSubject", back_populates="schedule_bindings")

    __table_args__ = (UniqueConstraint("group_id", "discipline_key", name="uq_schedule_binding"),)


class ScheduleNotificationLog(Base):
    __tablename__ = "schedule_notification_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    group_id: Mapped[int] = mapped_column(ForeignKey("groups.id"), nullable=False)
    discipline_key: Mapped[str] = mapped_column(String(255), nullable=False)
    pair_start_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    message_text: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("group_id", "discipline_key", "pair_start_at", name="uq_schedule_notification"),
    )
