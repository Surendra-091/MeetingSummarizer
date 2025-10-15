from pydantic import BaseModel
from typing import List, Optional

class ActionItem(BaseModel):
    text: str
    owner: Optional[str] = None
    due: Optional[str] = None  # suggested due date (string)

class MeetingResult(BaseModel):
    id: str
    filename: str
    transcript: str
    summary: str
    decisions: List[str]
    action_items: List[ActionItem]
