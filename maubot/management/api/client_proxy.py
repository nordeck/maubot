# maubot - A plugin-based Matrix bot system.
# Copyright (C) 2018 Tulir Asokan
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.
from aiohttp import web, client as http

from ...client import Client
from .base import routes
from .responses import resp

PROXY_CHUNK_SIZE = 32 * 1024


@routes.view("/proxy/{id}/{path:_matrix/.+}")
async def proxy(request: web.Request) -> web.StreamResponse:
    user_id = request.match_info.get("id", None)
    client = Client.get(user_id, None)
    if not client:
        return resp.client_not_found

    path = request.match_info.get("path", None)
    query = request.query.copy()
    try:
        del query["access_token"]
    except KeyError:
        pass
    headers = request.headers.copy()
    headers["Authorization"] = f"Bearer {client.access_token}"
    if "X-Forwarded-For" not in headers:
        peer = request.transport.get_extra_info("peername")
        if peer is not None:
            host, port = peer
            headers["X-Forwarded-For"] = f"{host}:{port}"

    data = await request.read()
    chunked = PROXY_CHUNK_SIZE if not data else None
    async with http.request(request.method, f"{client.homeserver}/{path}", headers=headers,
                            params=query, chunked=chunked, data=data) as proxy_resp:
        response = web.StreamResponse(status=proxy_resp.status, headers=proxy_resp.headers)
        await response.prepare(request)
        content = proxy_resp.content
        chunk = await content.read(PROXY_CHUNK_SIZE)
        while chunk:
            await response.write(chunk)
            chunk = await content.read(PROXY_CHUNK_SIZE)
        await response.write_eof()
        return response