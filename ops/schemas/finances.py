from typing import Literal, TypedDict

from .common import Period


class ExtractedTransaction(TypedDict, total=False):
    transaction_id: str
    date: str | None
    description: str
    source_description: str
    amount: int | float
    flow: Literal["income", "expense", "opening_balance"]
    category: str
    accounting_class: Literal["income", "opex", "capex", "opening_balance"]
    recurrence: Literal["recurring", "one_off", "not_applicable"]
    tags: list[str]
    source_page: int


class FinancialImport(TypedDict):
    source_document: str
    period: Period
    opening_balance: int | float
    transactions: list[ExtractedTransaction]
    reported_closing_balance: int | float
