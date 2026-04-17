import pytest

from src.ingestors.github_ingestor import GitHubIngestor


def test_extract_jira_keys():
    ingestor = GitHubIngestor(token="test_token")

    text = "This PR fixes PROJ-123 and TEAM-456"
    keys = ingestor.extract_jira_keys(text)

    assert "PROJ-123" in keys
    assert "TEAM-456" in keys
    assert len(keys) == 2


def test_extract_jira_keys_empty():
    ingestor = GitHubIngestor(token="test_token")

    text = "This PR has no Jira keys"
    keys = ingestor.extract_jira_keys(text)

    assert len(keys) == 0


def test_extract_jira_keys_none():
    ingestor = GitHubIngestor(token="test_token")

    keys = ingestor.extract_jira_keys(None)

    assert len(keys) == 0


def test_extract_jira_keys_duplicates():
    ingestor = GitHubIngestor(token="test_token")

    text = "PROJ-123 is mentioned twice: PROJ-123"
    keys = ingestor.extract_jira_keys(text)

    assert len(keys) == 1
    assert "PROJ-123" in keys
