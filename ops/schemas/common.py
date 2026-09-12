from typing import Literal, TypedDict

Risk = Literal["low", "content", "financial", "destructive", "publish"]


class Period(TypedDict, total=False):
    period_id: str
    display_label: str
    source_label: str
    period_type: str
    start_date: str
    end_date: str
    allowed_out_of_period_dates: list[str]
