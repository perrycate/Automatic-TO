from urllib import request, parse, error
import json


# Makes a request to the given url (base+additional) and the given parameters.
# If data is set, it should be a dictionary, which will be encoded as JSON.
# This will make the request a POST request instead of GET
def make_request(base_url, additional_url, params={}, data=None, raise_exception_on_http_error=False):
    """Fetches resource at URL, converts JSON response to object."""

    url = base_url + additional_url
    first_item = True
    for param, value in params.items():
        if first_item:
            url += f'?{param}={value}'
            first_item = False
            continue

        url += f'&{param}={value}'

    headers = {}
    if data is not None:
        data = json.dumps(data).encode()
        headers['Content-Type'] = 'application/json'
    try:
        r = request.Request(url, data, headers)
        response = request.urlopen(r)
    except error.HTTPError as e:
        # Usually we want to return any data on an HTTP error,
        # but sometimes we may wish to still treat it as an exception.
        if raise_exception_on_http_error:
            raise error.HTTPError from e
        response = e

    # Convert raw response to usable JSON object
    response_as_string = response.read().decode('utf-8')
    return json.loads(response_as_string)