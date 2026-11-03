from uuid import UUID, uuid4

from psycopg import sql
from psycopg.rows import dict_row

from bootstrap.database import Database
from taskapp.schemas import Task, TaskCreate, TaskFilter, TaskPatch


class TaskRepository:
    def __init__(self, database: Database) -> None:
        self.database = database

    def list(self, status: TaskFilter) -> list[Task]:
        query = "SELECT * FROM agentops_tasks"
        params: tuple[bool, ...] = ()
        if status != "all":
            query += " WHERE completed = %s"
            params = (status == "completed",)
        query += " ORDER BY created_at DESC, id"
        with self.database.connect() as conn, conn.cursor(row_factory=dict_row) as cursor:
            rows = cursor.execute(query, params).fetchall()
        return [Task.model_validate(row) for row in rows]

    def create(self, data: TaskCreate) -> Task:
        with self.database.connect() as conn, conn.cursor(row_factory=dict_row) as cursor:
            row = cursor.execute(
                """INSERT INTO agentops_tasks (id, title, description) VALUES (%s, %s, %s)
                   RETURNING *""",
                (uuid4(), data.title, data.description),
            ).fetchone()
        return Task.model_validate(row)

    def get(self, task_id: UUID) -> Task | None:
        with self.database.connect() as conn, conn.cursor(row_factory=dict_row) as cursor:
            row = cursor.execute(
                "SELECT * FROM agentops_tasks WHERE id = %s", (task_id,)
            ).fetchone()
        return Task.model_validate(row) if row else None

    def update(self, task_id: UUID, data: TaskPatch) -> Task | None:
        changes = data.model_dump(exclude_unset=True)
        # Los nombres salen del schema cerrado, no de SQL recibido del usuario.
        fields = sql.SQL(", ").join(
            sql.SQL("{} = %s").format(sql.Identifier(name)) for name in changes
        )
        query = sql.SQL(
            "UPDATE agentops_tasks SET {}, updated_at = now() WHERE id = %s RETURNING *"
        ).format(fields)
        with self.database.connect() as conn, conn.cursor(row_factory=dict_row) as cursor:
            row = cursor.execute(query, [*changes.values(), task_id]).fetchone()
        return Task.model_validate(row) if row else None

    def delete(self, task_id: UUID) -> bool:
        with self.database.connect() as conn:
            row = conn.execute(
                "DELETE FROM agentops_tasks WHERE id = %s RETURNING id", (task_id,)
            ).fetchone()
        return row is not None
