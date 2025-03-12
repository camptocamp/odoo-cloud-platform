# Copyright 2016-2024 Camptocamp SA
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html)

import json
from datetime import date, datetime
from typing import Any

import dateutil.parser


class SessionEncoder(json.JSONEncoder):
    """Encode date/datetime objects

    So that we can later recompose them if they were stored in the session
    """

    def default(self, obj: Any) -> Any:
        if isinstance(obj, datetime):
            return {"_type": "datetime_isoformat", "value": obj.isoformat()}
        if isinstance(obj, date):
            return {"_type": "date_isoformat", "value": obj.isoformat()}
        if isinstance(obj, set):
            return {"_type": "set", "value": tuple(sorted(obj))}
        return super().default(obj)


class SessionDecoder(json.JSONDecoder):
    """Decode json, recomposing recordsets and date/datetime"""

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, object_hook=self.object_hook, **kwargs)

    def object_hook(self, obj: dict[str, Any]) -> Any:
        """Convert serialized data back into its original Python type."""
        if "_type" not in obj:
            return obj
        if obj["_type"] == "datetime_isoformat":
            return dateutil.parser.parse(obj["value"])
        if obj["_type"] == "date_isoformat":
            return dateutil.parser.parse(obj["value"]).date()
        if obj["_type"] == "set":
            return set(obj["value"])
        return obj
