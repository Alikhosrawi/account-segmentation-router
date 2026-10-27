"""Data shapes (see DESIGN.md). TypedDicts only: documentation + editor help, no runtime cost."""
from typing import TypedDict, List, Literal
SegmentName = Literal['SMB', 'Mid-Market', 'Enterprise', 'Unknown']
Lane = Literal['ok', 'needs_human', 'none']
class Company(TypedDict):
    company: str; domain: str; ats: str; board_slug: str; hq_country: str
    headcount_band: str; headcount_source: str; hq_country: str; hq_basis: str; territory: str
class Posting(TypedDict):
    posting_id: str; company: str; domain: str; title: str; location: str; source_url: str; plain_text: str
class Signal(TypedDict):
    kind: Literal['fit', 'intent']; signal_type: str; posting_id: str; evidence_quote: str; confidence: float
class Score(TypedDict):
    fit: int; intent: int; signals: List[Signal]; prompt_version: str; guard_flags: List[str]; lane: Lane
class SdrAssignment(TypedDict):
    sdr_id: str; sdr_name: str; rule: str; queue: Literal['assigned', 'overflow', 'needs_human']
