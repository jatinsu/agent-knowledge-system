from datetime import datetime
from typing import Optional

from sqlalchemy import ForeignKey, Text, DateTime, Integer, SmallInteger, BigInteger, String
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

class Project(Base):
    __tablename__ = "projects"

    project_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    project_key: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    issues: Mapped[list["Issue"]] = relationship(back_populates="project")


class IssueType(Base):
    __tablename__ = "issue_types"

    issue_type_id: Mapped[int] = mapped_column(SmallInteger, primary_key=True)
    name: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    hierarchy_level: Mapped[int] = mapped_column(SmallInteger, nullable=False)

    issues: Mapped[list["Issue"]] = relationship(back_populates="issue_type")


class Issue(Base):
    __tablename__ = "issues"

    issue_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    project_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("projects.project_id"), nullable=False)
    issue_type_id: Mapped[int] = mapped_column(SmallInteger, ForeignKey("issue_types.issue_type_id"), nullable=False)
    parent_issue_id: Mapped[Optional[int]] = mapped_column(BigInteger, ForeignKey("issues.issue_id"), nullable=True)

    key: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    summary: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    status: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    priority: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    assignee_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    reporter_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    due_date: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    project: Mapped["Project"] = relationship(back_populates="issues")
    issue_type: Mapped["IssueType"] = relationship(back_populates="issues")
    parent: Mapped[Optional["Issue"]] = relationship(back_populates="children", remote_side=[issue_id])
    children: Mapped[list["Issue"]] = relationship(back_populates="parent")
    outgoing_links: Mapped[list["IssueLink"]] = relationship(
        foreign_keys="IssueLink.source_issue_id", back_populates="source_issue"
    )
    incoming_links: Mapped[list["IssueLink"]] = relationship(
        foreign_keys="IssueLink.target_issue_id", back_populates="target_issue"
    )


class IssueLink(Base):
    __tablename__ = "issue_links"

    link_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    source_issue_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("issues.issue_id"), nullable=False)
    target_issue_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("issues.issue_id"), nullable=False)
    link_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    source_issue: Mapped["Issue"] = relationship(foreign_keys=[source_issue_id], back_populates="outgoing_links")
    target_issue: Mapped["Issue"] = relationship(foreign_keys=[target_issue_id], back_populates="incoming_links")


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
