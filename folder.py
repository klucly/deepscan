from dataclasses import dataclass

@dataclass
class FolderUI:
    path: str
    title: str
    offset: float
    weight: int
    parent: object = None
    relative_weight: float = 0
    