# Copyright 2016-2019 Camptocamp SA
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html)

import re
from typing import Optional

class S3Uri:
    _url_re = re.compile(r"^s3://+([^/]+)/?(.*)", re.IGNORECASE | re.UNICODE)

    def __init__(self, uri: str) -> None:
        match = self._url_re.match(uri)
        if not match:
            raise ValueError(f"{uri}: is not a valid S3 URI")
        
        self._bucket: str = match.group(1)
        self._item: Optional[str] = match.group(2) if match.group(2) else None

    @property
    def bucket(self) -> str:
        return self._bucket

    @property
    def item(self) -> Optional[str]:
        return self._item
