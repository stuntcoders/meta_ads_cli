"""Generated pending-request stub for unit tests; integration uses real requests."""
from types import SimpleNamespace
from unittest.mock import Mock

from facebook_business.adobjects.objectparser import ObjectParser


class PendingMutationMock(Mock):
    def __init__(self, target_class, *, object_id=None, **kwargs):
        super().__init__(**kwargs)
        self.target_class = target_class
        self.object_id = object_id

    def __call__(self, *args, **kwargs):
        assert kwargs.get("pending") is True
        response = super().__call__(*args, **kwargs)
        parser = (ObjectParser(reuse_object=self.target_class(self.object_id))
                  if self.object_id else ObjectParser(target_class=self.target_class))
        request = SimpleNamespace(_response_parser=parser)

        def execute():
            data = response.export_all_data() if hasattr(response, "export_all_data") else response
            return request._response_parser.parse_single(data)

        request.execute = execute
        return request
