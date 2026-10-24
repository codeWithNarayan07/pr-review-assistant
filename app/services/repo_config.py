"""Optional per-repo settings read from `.pr-assistant.yml` on the PR's head commit."""

import logging

import yaml
from pydantic import BaseModel, Field, ValidationError

from app.errors import GitHubError

log = logging.getLogger(__name__)
CONFIG_PATH = ".pr-assistant.yml"


class CustomRisk(BaseModel):
    pattern: str = Field(min_length=1, max_length=200)  # glob, e.g. "src/payments/*"
    message: str = Field(min_length=1, max_length=200)


class RepoConfig(BaseModel):
    enabled: bool = True
    ignore_paths: list[str] = Field(default_factory=list, max_length=50)
    extra_checklist: list[str] = Field(default_factory=list, max_length=10)
    custom_risks: list[CustomRisk] = Field(default_factory=list, max_length=20)


async def load_repo_config(gh, repo: str, ref: str) -> RepoConfig:
    try:
        raw = await gh.get_file_content(repo, CONFIG_PATH, ref)
    except GitHubError:
        log.warning("could not read %s, using defaults", CONFIG_PATH, extra={"repo": repo})
        return RepoConfig()
    if raw is None:
        return RepoConfig()
    try:
        return RepoConfig.model_validate(yaml.safe_load(raw) or {})
    except (yaml.YAMLError, ValidationError):
        log.warning("invalid %s, using defaults", CONFIG_PATH, extra={"repo": repo})
        return RepoConfig()
