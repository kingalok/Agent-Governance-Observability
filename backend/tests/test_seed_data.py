from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from app.db import Base
from app.models import Agent, AgentTool, Approval, Policy, RiskTier, Run, RunEvent, UsageSnapshot
from app.services.seed import seed_demo_data


def build_session() -> Session:
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    session_local = sessionmaker(bind=engine, autoflush=False, autocommit=False, class_=Session)
    return session_local()


def test_seed_demo_data_loads_expected_records() -> None:
    db = build_session()

    seed_demo_data(db)
    seed_demo_data(db)

    agents = db.scalars(select(Agent).order_by(Agent.id.asc())).all()
    policies = db.scalars(select(Policy)).all()
    tools = db.scalars(select(AgentTool)).all()
    runs = db.scalars(select(Run)).all()
    approvals = db.scalars(select(Approval)).all()
    events = db.scalars(select(RunEvent)).all()
    usage = db.scalars(select(UsageSnapshot)).all()

    assert len(agents) == 2
    assert {agent.default_risk_tier for agent in agents} == {RiskTier.LOW, RiskTier.HIGH}
    assert len(policies) == 1
    assert policies[0].name == "Block Email Without Approval"
    assert len(tools) == 3
    assert len(runs) == 2
    assert len(approvals) == 1
    assert len(events) == 2
    assert len(usage) == 2
