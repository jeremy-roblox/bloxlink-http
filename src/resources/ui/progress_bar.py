from bloxlink_lib import BaseModel

LINE = "▬"

class ProgressBar(BaseModel):
    """Represents a progress bar UI."""

    progress: int
    total: int
    length: int = 10

    def __str__(self) -> str:
        """The string representation of this progress bar."""

        percent_done = int((self.progress / self.total)) * self.length

        return f"{percent_done * f"[{LINE}](https://blox.link)"}{LINE * (self.length - percent_done)}"
