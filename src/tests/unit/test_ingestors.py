import pytest

from src.ingestors.github_ingestor import GitHubIngestor


def test_extract_jira_keys():
    text = "This PR fixes PROJ-123 and TEAM-456"
    keys = GitHubIngestor.extract_jira_keys(text)

    assert "PROJ-123" in keys
    assert "TEAM-456" in keys
    assert len(keys) == 2


def test_extract_jira_keys_empty():
    text = "This PR has no Jira keys"
    keys = GitHubIngestor.extract_jira_keys(text)

    assert len(keys) == 0


def test_extract_jira_keys_none():
    keys = GitHubIngestor.extract_jira_keys(None)

    assert len(keys) == 0


def test_extract_jira_keys_duplicates():
    text = "PROJ-123 is mentioned twice: PROJ-123"
    keys = GitHubIngestor.extract_jira_keys(text)

    assert len(keys) == 1
    assert "PROJ-123" in keys
