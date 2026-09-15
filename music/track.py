from dataclasses import dataclass
from typing import Optional, Union, Any
import discord
from ui.theme import format_time

@dataclass
class Track:
    title: str
    artist: str
    duration: float  # seconds
    filepath: str
    requester: Optional[Union[discord.Member, discord.User, discord.ClientUser, Any]] = None
    thumbnail_url: Optional[str] = None
    source_type: str = "local"

    @property
    def formatted_duration(self) -> str:
        return format_time(self.duration)

    @property
    def display_name(self) -> str:
        return f"{self.title} - {self.artist}"

    def get_requester_display(self) -> str:
        if self.requester:
            return getattr(self.requester, "display_name", str(self.requester))
        return "Unknown"
