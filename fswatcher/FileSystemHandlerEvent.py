from dataclasses import dataclass
from watchdog.events import (
    FileCreatedEvent,
    FileModifiedEvent,
    FileMovedEvent,
    FileDeletedEvent,
)


@dataclass(frozen=True)
class FileSystemHandlerEvent:
    """
    Dataclass to hold the FileSystemHandler Configuration
    It is frozen to make it immutable
    """

    watch_path: str
    src_path: str
    bucket_name: str
    dest_path: str = ""
    action_type: str = ""
    completed: bool = False

    def __post_init__(self):
        event_types = {
            FileCreatedEvent: "CREATE",
            FileModifiedEvent: "UPDATE",
            FileMovedEvent: "PUT",
            FileDeletedEvent: "DELETE",
        }

        for event_class, action in event_types.items():
            if isinstance(self.src_path, event_class):
                self.action_type = action
                break

    def __repr__(self) -> str:
        return f"FileSystemHandlerEvent(src_path={self.src_path}, bucket_name={self.bucket_name}, dest_path={self.dest_path}, action_type={self.action_type}, completed={self.completed})"

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, FileSystemHandlerEvent):
            raise ValueError("The other object is not of the same type")

        return (
            self.src_path == other.src_path
            and self.bucket_name == other.bucket_name
            and self.dest_path == other.dest_path
            and self.action_type == other.action_type
        )

    def get_log_message(self) -> str:
        return f"Object ({self.get_parsed_path()}) - File {self.get_capitalized_action_type()}: {self.get_parsed_path() + (f' to {self.dest_path}' if self.dest_path != '' else self.dest_path)}"

    def is_completed(self) -> bool:
        return self.completed

    def get_capitalized_action_type(self) -> str:
        return self.action_type.capitalize()

    def get_path(self) -> str:
        return self.src_path if self.dest_path == "" else self.dest_path

    def get_parsed_path(self) -> str:
        path = self.get_path()
        parsed_src_path = path.split(self.watch_path, 1)
        merged_path = "".join(parsed_src_path)

        return merged_path.lstrip("/")
