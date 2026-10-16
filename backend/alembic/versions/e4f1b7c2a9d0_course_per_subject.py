"""course_per_subject: un curso por asignatura y unidades con fuente

Revision ID: e4f1b7c2a9d0
Revises: d2e8a20b3f8a
Create Date: 2026-10-13 10:30:00

"""
import re
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "e4f1b7c2a9d0"
down_revision: Union[str, None] = "d2e8a20b3f8a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_GEN = re.compile(r"^g(\d+)-")


def upgrade() -> None:
    with op.batch_alter_table("course_units") as batch:
        batch.add_column(sa.Column("source", sa.String(length=64), nullable=False, server_default=""))

    conn = op.get_bind()
    courses = {cid: slug for cid, slug in conn.execute(sa.text("SELECT id, slug FROM courses"))}
    # Fuente de cada unidad: "g<id>" si vino del generador, si no el slug de su curso.
    for uid, cid, ref in conn.execute(sa.text("SELECT id, course_id, ref FROM course_units")).fetchall():
        m = _GEN.match(ref)
        conn.execute(sa.text("UPDATE course_units SET source = :s WHERE id = :id"), {"s": f"g{m.group(1)}" if m else courses.get(cid, ""), "id": uid})

    # Varios cursos de la misma asignatura → se fusionan en el más antiguo (sin perder progreso).
    rows = conn.execute(sa.text("SELECT id, subject_id FROM courses WHERE subject_id IS NOT NULL ORDER BY id")).fetchall()
    keep: dict[int, int] = {}
    merged: set[int] = set()
    for cid, sid in rows:
        if sid not in keep:
            keep[sid] = cid
            continue
        target = keep[sid]
        start = conn.execute(sa.text("SELECT COUNT(*) FROM course_units WHERE course_id = :t"), {"t": target}).scalar() or 0
        units = conn.execute(sa.text("SELECT id FROM course_units WHERE course_id = :c ORDER BY position, id"), {"c": cid}).fetchall()
        for i, (uid,) in enumerate(units):
            conn.execute(sa.text("UPDATE course_units SET course_id = :t, position = :p WHERE id = :id"), {"t": target, "p": start + i, "id": uid})
        conn.execute(sa.text("DELETE FROM courses WHERE id = :c"), {"c": cid})
        merged.add(target)
    # En los cursos fusionados, las unidades del generador van en el orden en que se generaron.
    for target in merged:
        units = conn.execute(sa.text("SELECT id, source, position FROM course_units WHERE course_id = :t"), {"t": target}).fetchall()
        def key(row):
            m = re.match(r"^g(\d+)$", row[1] or "")
            return (int(m.group(1)) if m else 0, row[2], row[0])
        for pos, (uid, _src, _p) in enumerate(sorted(units, key=key)):
            conn.execute(sa.text("UPDATE course_units SET position = :p WHERE id = :id"), {"p": pos, "id": uid})
    # El título del curso es el de su asignatura.
    conn.execute(sa.text("UPDATE courses SET title = (SELECT name FROM subjects WHERE subjects.id = courses.subject_id) WHERE subject_id IS NOT NULL"))

    with op.batch_alter_table("courses") as batch:
        batch.create_unique_constraint("uq_courses_subject_id", ["subject_id"])


def downgrade() -> None:
    with op.batch_alter_table("courses") as batch:
        batch.drop_constraint("uq_courses_subject_id", type_="unique")
    with op.batch_alter_table("course_units") as batch:
        batch.drop_column("source")
