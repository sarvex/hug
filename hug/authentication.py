"""hug/authentication.py

Provides the basic built-in authentication helper functions

Copyright (C) 2016  Timothy Edmund Crosley

Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
documentation files (the "Software"), to deal in the Software without restriction, including without limitation
the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and
to permit persons to whom the Software is furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all copies or
substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED
TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL
THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF
CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR
OTHER DEALINGS IN THE SOFTWARE.

"""
from __future__ import absolute_import

import base64
import binascii

from falcon import HTTPUnauthorized


def authenticator(function, challenges=()):
    """Wraps authentication logic, verify_user through to the authentication function.

    The verify_user function passed in should accept an API key and return a user object to
    store in the request context if authentication succeeded.
    """
    challenges = challenges or ('{} realm="simple"'.format(function.__name__),)

    def wrapper(verify_user):
        def authenticate(request, response, **kwargs):
            result = function(request, response, verify_user, **kwargs)

            def authenticator_name():
                try:
                    return function.__doc__.splitlines()[0]
                except AttributeError:
                    return function.__name__

            if result is None:
                raise HTTPUnauthorized(
                    "Authentication Required",
                    "Please provide valid {0} credentials".format(authenticator_name()),
                    challenges=challenges,
                )

            if result is False:
                raise HTTPUnauthorized(
                    "Invalid Authentication",
                    "Provided {0} credentials were invalid".format(authenticator_name()),
                    challenges=challenges,
                )

            request.context["user"] = result
            return True

        authenticate.__doc__ = function.__doc__
        return authenticate

    return wrapper


@authenticator
def basic(request, response, verify_user, realm="simple", context=None, **kwargs):
    """Basic HTTP Authentication"""
    http_auth = request.auth
    response.set_header("WWW-Authenticate", "Basic")
    if http_auth is None:
        return

    if isinstance(http_auth, bytes):
        http_auth = http_auth.decode("utf8")
    try:
        auth_type, user_and_key = http_auth.split(" ", 1)
    except ValueError:
        raise HTTPUnauthorized(
            "Authentication Error",
            "Authentication header is improperly formed",
            challenges=(f'Basic realm="{realm}"',),
        )

    if auth_type.lower() == "basic":
        try:
            user_id, key = (
                base64.decodebytes(bytes(user_and_key.strip(), "utf8")).decode("utf8").split(":", 1)
            )
            try:
                user = verify_user(user_id, key)
            except TypeError:
                user = verify_user(user_id, key, context)
            if user:
                response.set_header("WWW-Authenticate", "")
                return user
        except (binascii.Error, ValueError):
            raise HTTPUnauthorized(
                "Authentication Error",
                "Unable to determine user and password with provided encoding",
                challenges=(f'Basic realm="{realm}"',),
            )
    return False


@authenticator
def api_key(request, response, verify_user, context=None, **kwargs):
    """API Key Header Authentication

    The verify_user function passed in to ths authenticator shall receive an
    API key as input, and return a user object to store in the request context
    if the request was successful.
    """
    if api_key := request.get_header("X-Api-Key"):
        try:
            user = verify_user(api_key)
        except TypeError:
            user = verify_user(api_key, context)
        return user if user else False
    else:
        return None


@authenticator
def token(request, response, verify_user, context=None, **kwargs):
    """Token verification

    Checks for the Authorization header and verifies using the verify_user function
    """
    if token := request.get_header("Authorization"):
        try:
            verified_token = verify_user(token)
        except TypeError:
            verified_token = verify_user(token, context)
        return verified_token if verified_token else False
    return None


def verify(user, password):
    """Returns a simple verification callback that simply verifies that the users and password match that provided"""

    def verify_user(user_name, user_password):
        return user_name if user_name == user and user_password == password else False

    return verify_user
