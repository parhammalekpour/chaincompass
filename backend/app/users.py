from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from typing import Literal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db.models.auth import User
from app.db.session import SessionFactory

logger = logging.getLogger("app.users")
UserRole = Literal["user", "admin"]


async def set_user_role(
    email: str,
    role: UserRole,
    *,
    session_factory: async_sessionmaker[AsyncSession] = SessionFactory,
) -> bool:
    async with session_factory() as session:
        user = await session.scalar(
            select(User).where(func.lower(User.email) == email.strip().lower())
        )
        if user is None:
            return False
        user.role = role
        await session.commit()
        logger.info("user_role_updated user_id=%s role=%s", user.id, role)
    return True


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Manage ChainCompass user roles")
    commands = parser.add_subparsers(dest="command", required=True)
    set_role = commands.add_parser("set-role")
    set_role.add_argument("--email", required=True)
    set_role.add_argument("--role", choices=("user", "admin"), required=True)
    return parser.parse_args(argv)


async def execute_command(
    argv: list[str],
    *,
    session_factory: async_sessionmaker[AsyncSession] = SessionFactory,
) -> int:
    args = parse_args(argv)
    if args.command == "set-role":
        updated = await set_user_role(
            args.email,
            args.role,
            session_factory=session_factory,
        )
        if not updated:
            print("No user found with that email.", file=sys.stderr)
            return 1
        print(f"User role updated to {args.role}.")
    return 0


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    raise SystemExit(asyncio.run(execute_command(sys.argv[1:])))


if __name__ == "__main__":
    main()
