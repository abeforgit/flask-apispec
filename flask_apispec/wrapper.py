# -*- coding: utf-8 -*-
try:
    from collections.abc import Mapping
except ImportError:  # Python 2
    from collections import Mapping


import flask
import marshmallow as ma
import werkzeug
from six.moves import http_client as http
from webargs import flaskparser

from flask_apispec import utils


MARSHMALLOW_VERSION_INFO = tuple(
    [int(part) for part in ma.__version__.split('.') if part.isdigit()]
)

class Wrapper(object):
    """Apply annotations to a view function.

    :param func: View function to wrap
    :param instance: Optional instance or parent
    """
    def __init__(self, func, instance=None):
        self.func = func
        self.instance = instance

    def __call__(self, *args, **kwargs):
        response = self.call_view(*args, **kwargs)
        if isinstance(response, werkzeug.Response):
            return response
        unpacked = unpack(response)
        status_code = unpacked[1] or http.OK
        return self.marshal_result(unpacked, status_code)

    def call_view(self, *args, **kwargs):
        config = flask.current_app.config
        parser = config.get('APISPEC_WEBARGS_PARSER', flaskparser.parser)
        annotation = utils.resolve_annotations(self.func, 'args', self.instance)
        if annotation.apply is not False:
            for option in annotation.options:
                schema = utils.resolve_schema(option['args'], request=flask.request)
                parsed = parser.parse(schema, locations=option['kwargs']['locations'])
                if getattr(schema, 'many', False):
                    args += tuple(parsed)
                elif isinstance(parsed, Mapping):
                    kwargs.update(parsed)
                else:
                    args += (parsed, )

        return self.func(*args, **kwargs)

    def marshal_result(self, unpacked, status_code):
        config = flask.current_app.config
        format_response = config.get('APISPEC_FORMAT_RESPONSE', flask.jsonify) or identity
        annotation = utils.resolve_annotations(self.func, 'schemas', self.instance)
        schemas = utils.merge_recursive(annotation.options)
        schema = schemas.get(status_code, schemas.get('default'))
        if schema and annotation.apply is not False:
            schema = utils.resolve_schema(schema['schema'], request=flask.request)
            dumped = schema.dump(unpacked[0])
            output = dumped.data if MARSHMALLOW_VERSION_INFO[0] < 3 else dumped
        else:
            output = format_response(unpacked[0])
        return format_output((output, ) + unpacked[1:])

def identity(value):
    return value

def unpack(resp):
    resp = resp if isinstance(resp, tuple) else (resp, )
    return resp + (None, ) * (3 - len(resp))

def format_output(values):
    while values[-1] is None:
        values = values[:-1]
    return values if len(values) > 1 else values[0]
