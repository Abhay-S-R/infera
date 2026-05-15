from sqlalchemy import Boolean, Column, Integer, String, Text, JSON, DateTime, Float, func
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


class WebhookEvent(Base):
    __tablename__ = "webhook_events"

    id = Column(Integer, primary_key=True, index=True)
    source = Column(String(64), nullable=False, default="news")
    title = Column(String(500), nullable=False)
    url = Column(String(1024), nullable=True)
    payload = Column(JSON, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class Workflow(Base):
    __tablename__ = "workflows"

    id = Column(Integer, primary_key=True, index=True)
    webhook_id = Column(Integer, nullable=True, index=True)
    status = Column(String(32), nullable=False, default="pending")
    current_agent = Column(String(64), nullable=True)
    extra_data = Column(JSON, nullable=True)
    tokens_used = Column(Integer, nullable=True, default=0)
    estimated_cost = Column(Float, nullable=True, default=0.0)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class Competitor(Base):
    __tablename__ = "competitors"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(256), nullable=False)
    industry = Column(String(256), nullable=True)
    keywords = Column(JSON, nullable=False, default=list)
    active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class CompetitorProfileRow(Base):
    """Institutional memory per competitor (Phase 4)."""
    __tablename__ = "competitor_profiles"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(256), nullable=False, unique=True, index=True)
    profile = Column(JSON, nullable=False, default=dict)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class Report(Base):
    __tablename__ = "reports"

    id = Column(Integer, primary_key=True, index=True)
    workflow_id = Column(Integer, nullable=True, index=True)
    title = Column(String(500), nullable=False)
    status = Column(String(32), nullable=False, default="draft")
    markdown = Column(Text, nullable=True)
    documents = Column(JSON, nullable=True)
    confidence = Column(String(16), nullable=True)
    sources = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
