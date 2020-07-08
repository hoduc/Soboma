from dataclasses import dataclass, field
from typing import List, Type


@dataclass
class Pin:
    profile_url: str = ""
    created_at: str = ""
    content: str = ""
    media_urls: List[str] = field(default_factory=list)
    relations = []
