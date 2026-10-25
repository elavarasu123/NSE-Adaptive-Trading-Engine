from app.database import (
    SessionLocal,
    is_postgres,
)
from app.models import (
    Portfolio,
    Position,
)
from app.shared_state import (
    shared_state_enabled,
)


def main():
    db = SessionLocal()

    try:
        portfolio_count = (
            db.query(Portfolio)
            .count()
        )

        portfolio = (
            db.query(Portfolio)
            .first()
        )

        open_positions = (
            db.query(Position)
            .filter(
                Position.status
                == "OPEN"
            )
            .count()
        )

        print()
        print(
            "================================"
        )
        print(
            " V1.2 CLOUD DASHBOARD STATUS"
        )
        print(
            "================================"
        )

        print(
            "Database:",
            (
                "POSTGRESQL"
                if is_postgres()
                else "SQLITE"
            ),
        )

        print(
            "Shared state:",
            shared_state_enabled(),
        )

        print(
            "Portfolio rows:",
            portfolio_count,
        )

        if portfolio:
            print(
                "Initial capital:",
                portfolio.initial_capital,
            )

            print(
                "Cash:",
                portfolio.cash,
            )

        print(
            "Open positions:",
            open_positions,
        )

        print(
            "Paper only:",
            True,
        )

        print(
            "Live broker orders:",
            False,
        )

        print(
            "================================"
        )

    finally:
        db.close()


if __name__ == "__main__":
    main()
