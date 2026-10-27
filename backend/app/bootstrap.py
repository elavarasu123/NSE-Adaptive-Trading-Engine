from .database import (
    Base,
    SessionLocal,
    engine,
)
from .models import (
    Journal,
    Portfolio,
    StrategyVersion,
)


def ensure_paper_database():
    """
    Make a fresh ephemeral runner safe to use.

    Creates tables and seeds the ONE-TIME paper
    portfolio only when no portfolio exists.
    """
    Base.metadata.create_all(
        bind=engine
    )

    db = SessionLocal()

    created_portfolio = False
    created_strategy = False

    try:
        portfolio = (
            db.query(Portfolio)
            .first()
        )

        if portfolio is None:
            db.add(
                Portfolio(
                    id=1,
                    initial_capital=100000,
                    cash=100000,
                    realized_pnl=0,
                )
            )

            db.add(
                Journal(
                    kind="SYSTEM",
                    message=(
                        "Initialized one-time "
                        "₹1,00,000 paper capital."
                    ),
                )
            )

            created_portfolio = True

        strategy = (
            db.query(StrategyVersion)
            .filter(
                StrategyVersion.name
                == "champion-v0.2"
            )
            .first()
        )

        if strategy is None:
            db.add(
                StrategyVersion(
                    name="champion-v0.2",
                    role="CHAMPION",
                    description=(
                        "Frozen paper research "
                        "champion."
                    ),
                    active=True,
                )
            )

            created_strategy = True

        db.commit()

        portfolio = (
            db.query(Portfolio)
            .first()
        )

        return {
            "createdPortfolio":
                created_portfolio,
            "createdStrategy":
                created_strategy,
            "initialCapital":
                portfolio.initial_capital,
            "cash":
                portfolio.cash,
        }

    finally:
        db.close()
