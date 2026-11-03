"""Una imagen, dos procesos desplegados como servicios separados en Render."""

import os

import uvicorn


def main() -> None:
    roles = {"receiver": "bootstrap.main:app", "tasks": "taskapp.main:app"}
    role = os.getenv("SERVICE_ROLE", "receiver")
    if role not in roles:
        raise SystemExit("SERVICE_ROLE debe ser receiver o tasks")
    uvicorn.run(roles[role], host="0.0.0.0", port=int(os.getenv("PORT", "10000")), access_log=False)


if __name__ == "__main__":
    main()
