from dataclasses import dataclass, field
from typing import List, Type


@dataclass
class Pin:
    profile_name: str = ""
    profile_url: str = ""
    created_at: str = ""
    content: str = ""
    urls: List[str] = field(default_factory=list)
    media_urls: List[List[str]] = field(default_factory=list)
    relations = [] # not sure how to add this yet
