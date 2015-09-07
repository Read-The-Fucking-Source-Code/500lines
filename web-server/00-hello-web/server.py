#!/usr/bin/env python
# -*- coding: utf-8 -*-
from __future__ import absolute_import, print_function, unicode_literals

"""使用内置的 BaseHTTPServer 构建一个简单的 HTTP 服务器"""
import BaseHTTPServer

class RequestHandler(BaseHTTPServer.BaseHTTPRequestHandler):
    '''Handle HTTP requests by returning a fixed 'page'.'''

    # Page to send back.
    Page = '''\
<html>
<body>
<p>Hello, web!</p>
</body>
</html>
'''

    # Handle a GET request.
    # 处理一个 GET 请求
    def do_GET(self):
        self.send_response(200)    # HTTP/1.1 200 OK\r\n
                                   # Server: WSGI 1.0\r\n
                                   # Date: Mon, 07 Sep 2015 10:18:08 GMT\r\n
        self.send_header("Content-type", "text/html")            # Content-type: text/html\r\n
        self.send_header("Content-Length", str(len(self.Page)))  # Content-Length: 123\r\n
        self.end_headers()            # \r\n
        self.wfile.write(self.Page)   # body

#----------------------------------------------------------------------

if __name__ == '__main__':
    serverAddress = ('', 8080)
    server = BaseHTTPServer.HTTPServer(serverAddress, RequestHandler)
    server.serve_forever()   # 启动一个死循环服务，可以通过 Ctrl + c 终止
