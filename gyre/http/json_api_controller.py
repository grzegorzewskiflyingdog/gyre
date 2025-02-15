import json

from accept_types import get_best_match
from twisted.web import resource
from twisted.web.error import Error as WebError
from twisted.web.resource import ErrorPage, NoResource
from twisted.web.server import NOT_DONE_YET


class NotAcceptableResource(ErrorPage):
    def __init__(
        self, message="Sorry, Accept header does not match a type we can serve"
    ):
        super().__init__(416, "Not Acceptable", message)


class UnsupportedMediaTypeResource(ErrorPage):
    def __init__(
        self, message="Sorry, Content-Type header does not match a type we can process"
    ):
        super().__init__(415, "Unsupported Media Type", message)


class JSONAPIController(resource.Resource):
    preferred_return_type = "application/json"
    return_types = {"application/json"}

    def _render_common(self, request, handler, input):
        if not handler:
            return NoResource().render(request)

        # Calculate what (if any) return type matches the accept header
        return_type = None
        accept_header = request.getHeader("accept")

        if accept_header:
            return_type = get_best_match(
                accept_header, [self.preferred_return_type] + list(self.return_types)
            )

        # If none, throw an error
        if not return_type:
            return NotAcceptableResource().render(request)

        # Otherwise reset the request accept header to just the return type
        request.requestHeaders.setRawHeaders("accept", [return_type])

        try:
            response = handler(request, input)
        except ValueError as e:
            return ErrorPage(400, str(e), b"").render(request)
        except WebError as e:
            return ErrorPage(int(e.status), e.message, b"").render(request)
        except Exception as e:
            print(f"Exception in JSON controller {self.__class__.__name__}. ", e)
            return ErrorPage(500, b"Internal Error", b"").render(request)

        # Handle when a controller returns NOT_DONE_YET because it's
        # still working in the background
        if response is NOT_DONE_YET:
            return NOT_DONE_YET

        # Convert dict or object instances into json strings
        if isinstance(response, dict):
            response = json.dumps(response)

        # JSON is always encoded as utf-8
        if isinstance(response, str):
            response = response.encode("utf-8")

        # And return it
        request.setHeader("content-type", return_type)
        return response

    def render_GET(self, request):
        handler = getattr(self, "handle_GET", None)
        return self._render_common(request, handler, None)

    def render_POST(self, request):
        handler = getattr(self, "handle_POST", None)

        content_type_header = request.getHeader("content-type")
        if not content_type_header or content_type_header != "application/json":
            return UnsupportedMediaTypeResource().render(request)

        return self._render_common(request, handler, json.load(request.content))
