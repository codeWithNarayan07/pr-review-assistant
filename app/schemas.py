from dataclasses import dataclass

from pydantic import BaseModel, ConfigDict, Field


# ---- GitHub webhook payload (only the fields we use) ----
class _Head(BaseModel):
    model_config = ConfigDict(extra="ignore")
    sha: str


class _PullRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")
    number: int
    draft: bool = False
    head: _Head


class _Repository(BaseModel):
    model_config = ConfigDict(extra="ignore")
    full_name: str


class _Installation(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: int


class PullRequestEvent(BaseModel):
    model_config = ConfigDict(extra="ignore")
    action: str
    pull_request: _PullRequest
    repository: _Repository
    installation: _Installation | None = None


# ---- LLM output (validated so a bad model reply can never reach GitHub) ----
class LLMReview(BaseModel):
    summary: str = Field(min_length=1, max_length=900)
    key_changes: list[str] = Field(default_factory=list, max_length=8)
    risks: list[str] = Field(default_factory=list, max_length=6)
    checklist: list[str] = Field(default_factory=list, max_length=8)


# ---- internal data ----
@dataclass
class FileChange:
    path: str
    status: str
    additions: int
    deletions: int
    patch: str | None = None

    @property
    def changes(self) -> int:
        return self.additions + self.deletions


@dataclass
class ReviewContext:
    title: str
    description: str
    files_summary: str
    diff_text: str
