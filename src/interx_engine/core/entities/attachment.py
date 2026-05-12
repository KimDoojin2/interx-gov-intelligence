from dataclasses import dataclass


@dataclass
class Attachment:
    notice_id: str
    site: str
    notice_title: str
    detail_url: str
    file_index: int
    file_name: str
    source_url: str
    download_url: str
