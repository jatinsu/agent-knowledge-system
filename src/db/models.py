from datetime import datetime
from typing import Optional

from sqlalchemy import ForeignKey, Text, DateTime, Integer, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Repository(Base):
    __tablename__ = "repos"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255))
    owner: Mapped[str] = mapped_column(String(255))
    url: Mapped[str] = mapped_column(String(500))
    default_branch: Mapped[str] = mapped_column(String(100), default="main")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    pull_requests: Mapped[list["PullRequest"]] = relationship(back_populates="repository")
    features: Mapped[list["Feature"]] = relationship(back_populates="repository")


class PullRequest(Base):
    __tablename__ = "pull_requests"

    id: Mapped[int] = mapped_column(primary_key=True)
    repo_id: Mapped[int] = mapped_column(ForeignKey("repos.id"))
    pr_number: Mapped[int] = mapped_column(Integer)
    title: Mapped[str] = mapped_column(String(500))
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    author: Mapped[str] = mapped_column(String(255))
    state: Mapped[str] = mapped_column(String(50))
    base_branch: Mapped[str] = mapped_column(String(100))
    head_branch: Mapped[str] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(DateTime)
    merged_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    files_changed: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    epic_key: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    story_key: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    task_key: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    repository: Mapped["Repository"] = relationship(back_populates="pull_requests")
    features: Mapped[list["Feature"]] = relationship(
        secondary="feature_pr_association", back_populates="pull_requests"
    )


# --- JIRA_DB tables ---

class JiraProject(Base):
    __tablename__ = "jira_projects"

    id: Mapped[str] = mapped_column(String(50), primary_key=True)
    title: Mapped[str] = mapped_column(String(500))
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    date: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)


class JiraEpic(Base):
    __tablename__ = "jira_epics"

    id: Mapped[str] = mapped_column(String(50), primary_key=True)
    title: Mapped[str] = mapped_column(String(500))
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)


class JiraStory(Base):
    __tablename__ = "jira_stories"

    id: Mapped[str] = mapped_column(String(50), primary_key=True)
    title: Mapped[str] = mapped_column(String(500))
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)


class JiraTask(Base):
    __tablename__ = "jira_tasks"

    id: Mapped[str] = mapped_column(String(50), primary_key=True)
    title: Mapped[str] = mapped_column(String(500))
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)


class Feature(Base):
    __tablename__ = "features"

    id: Mapped[int] = mapped_column(primary_key=True)
    repo_id: Mapped[int] = mapped_column(ForeignKey("repos.id"))
    name: Mapped[str] = mapped_column(String(500))
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    components: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    repository: Mapped["Repository"] = relationship(back_populates="features")
    pull_requests: Mapped[list["PullRequest"]] = relationship(
        secondary="feature_pr_association", back_populates="features"
    )
    documents: Mapped[list["Document"]] = relationship(back_populates="feature")


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(primary_key=True)
    feature_id: Mapped[Optional[int]] = mapped_column(ForeignKey("features.id"), nullable=True)
    doc_type: Mapped[str] = mapped_column(String(50))
    title: Mapped[str] = mapped_column(String(500))
    file_path: Mapped[str] = mapped_column(String(500))
    graph_node_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    feature: Mapped[Optional["Feature"]] = relationship(back_populates="documents")


class GraphVersion(Base):
    __tablename__ = "graph_versions"

    id: Mapped[int] = mapped_column(primary_key=True)
    version: Mapped[str] = mapped_column(String(50))
    file_path: Mapped[str] = mapped_column(String(500))
    node_count: Mapped[int] = mapped_column(Integer)
    edge_count: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class FeaturePRAssociation(Base):
    __tablename__ = "feature_pr_association"

    feature_id: Mapped[int] = mapped_column(ForeignKey("features.id"), primary_key=True)
    pr_id: Mapped[int] = mapped_column(ForeignKey("pull_requests.id"), primary_key=True)
