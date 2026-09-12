from typing import TypedDict


class ApprovalRequest(TypedDict):
    proposal_id: str


class ExecuteRequest(TypedDict):
    proposal_id: str
    approval_token: str
