import os


def reserve(database, amount: int) -> bool:
    if not 0 < amount <= 400000:
        return False
    # Límite acumulado, compartido por Render y Actions. En demo se libera la reserva.
    cap = 10000000 if os.getenv("AGENTOPS_DEMO") == "1" else 5000000
    with database.connect() as conn:
        return (
            conn.execute(
                """UPDATE agentops_ai_budget SET reserved=reserved+%s
               WHERE singleton AND reserved+%s<=%s RETURNING reserved""",
                (amount, amount, cap),
            ).fetchone()
            is not None
        )
