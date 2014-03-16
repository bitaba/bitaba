#!/usr/bin/python2
#coding=utf-8

# Сделано на коленке, надо всё нахуй переделать
# Из-за особенностей API вся база сообщений запрашивается заново каждый раз, поэтому надо держать свою базу и обновлять её, реагируя на события

# API

import xmlrpclib
import json
from base64 import b64encode, b64decode

class API():
    def __init__(self, interface, port, username, password):
        self.api = xmlrpclib.ServerProxy("http://{}:{}@{}:{}/".format(username, password, interface, port))

        self.api.add(0, 1)

    def send_post(self, to, from_, subject, message):
        self.api.sendMessage(to, from_, b64encode(subject), b64encode(message))

    def __decode_post(self, post):
        subject = b64decode(post[u"subject"])
        re = subject[: 4] != "Re: "

        return {
            "ID": post[u"msgid"],
            "re": re,
            "poster": post[u"fromAddress"],
            "date": post[u"receivedTime"],
            "subject": subject if re else subject[4: ],
            "message": b64decode(post[u"message"])
        }

    def get_boards(self):
        for i in json.loads(self.api.listAddresses2())[u"addresses"]:
            if i[u"chan"]:
                yield {
                    "address": i[u"address"],
                    "label": b64decode(i[u"label"])
                }

    # Если задан ID, возвращает тред, иначе генератор списка тредов

    def get_threads(self, board, ID = None):
        temp = {}
        threads = {}

        for i in json.loads(self.api.getAllInboxMessages())[u"inboxMessages"]:
            if i[u"toAddress"] == board:
                post = self.__decode_post(i)

                thread = temp.get(post["subject"], {
                    "subject": post["subject"],
                    "oppost": None,
                    "replies": [],
                    "bumped": 0
                })

                temp[post["subject"]] = thread

                # Если заголовок поста начинался не с "Re: ", то это, вероятно, ОП-пост. Если существует два ОП-поста с одинаковым заголовком, то предпочтение отдаётся более раннему

                if post["re"]:
                    if thread["oppost"] is not None:
                        if thread["oppost"]["date"] < post["date"]:
                            thread["replies"].append(post)
                        else:
                            del threads[thread["oppost"]["ID"]]

                            thread["oppost"] = post
                            threads[post["ID"]] = thread
                    else:
                        thread["oppost"] = post
                        threads[post["ID"]] = thread
                else:
                    thread["replies"].append(post)

                # По дате получения последнего поста сортировать не совсем хорошо, но дату отправки я не нашёл
                # И сажи, кстати, нет

                thread["bumped"] = max(thread["bumped"], post["date"])

        if ID is not None:
            if ID in threads:
                threads[ID]["replies"].sort(key = lambda x: x["date"])

                return threads[ID]
        else:
            return (
                {
                    "ID": i,
                    "subject": threads[i]["subject"],
                    "oppost": threads[i]["oppost"],
                    "replies": len(threads[i]["replies"])
                } for i in sorted(threads, key = lambda x: threads[x]["bumped"], reverse = True)
            )

try:
    api = API("127.0.0.1", "8442", "ananas", "123456")
except:
    api = None

# Обработчики POST-запросов

from urlparse import parse_qs
from cgi import parse_header, parse_multipart
from imghdr import what

def connect_action(server):
    global api

    query = parse_qs(server.rfile.read(int(server.headers["Content-Length"])))

    if (
        "interface" in query and
        "port" in query and
        "username" in query and
        "password" in query
    ):
        try: api = API( query["interface"][0],
                query["port"][0],
                query["username"][0],
                query["password"][0]
            )
        except:
            api = None

        server.send_response(302)
        server.send_header("Location", "")

def send_action(server):
    if "Content-Type" in server.headers:
        header = parse_header(server.headers["Content-Type"])

        if header[0] == "multipart/form-data":
            query = parse_multipart(server.rfile, header[1])

            if (
                "from" in query and
                "to" in query and
                "subject" in query and
                "message" in query and
                "image" in query
            ):
                if query["image"][0]:
                    format = what("", query["image"][0])

                    if format in ("jpeg", "png", "gif"):
                        query["message"][0] += "\ndata:image/{};base64,{}".format(format, b64encode(query["image"][0]))

                print api.send_post(
                    query["to"][0],
                    query["from"][0],
                    query["subject"][0],
                    query["message"][0]
                )

            server.send_response(302)
            server.send_header("Location", "")

# Обработчики GET-запросов

from cgi import escape
from datetime import datetime

def page_head(server, title):
    server.send_response(200)
    server.send_header("Content-Type", "text/html; charset=UTF-8")
    server.end_headers()

    # мне так удобнее
    pre_style="body { margin: 0; padding: 8px; margin-bottom: auto; }blockquote blockquote { margin-left: 0em }form { margin-bottom: 0px }form .trap { display:none }.postarea { text-align: center }.postarea table { margin: 0px auto; text-align: left }.thumb { border: none; float: left; margin: 2px 20px }.nothumb { float: left; background: #eee; border: 2px dashed #aaa; text-align: center; margin: 2px 20px; padding: 1em 0.5em 1em 0.5em; }.reply blockquote, blockquote :last-child { margin-bottom: 0em }.reflink a { color: inherit; text-decoration: none }.reply .filesize { margin-left: 20px }.userdelete { float: right; text-align: center; white-space: nowrap }.replypage .replylink { display: none }"
    style="html,body{background-color:#EEEEEE;color:#333333;font-family:Trebuchet MS,Trebuchet,tahoma,serif;}a{color:#FF6600;}a:hover{color:#0066FF;}.adminbar{clear:both;float:right;font-size:.8em;}.adminbar a{font-weight:bold;}.logo{clear:both;text-align:left;font-size:2em;font-weight:bold;color:#FF6600;}.thumb{border:medium none;float:left;margin:3px 20px;}.logo2{text-align:center;}.theader,.passvalid{background:#DDDDDD;text-align:center;padding:2px;color:#2266AA;clear:both;font-weight:bold;margin-bottom:.5em;border:solid 1px #CCCCCC;border-radius:5px;-moz-border-radius:5px;-webkit-border-radius:5px;}.postarea{}.rules{}iframe{margin:3px 20px;float:left;}.postblock{background:transparent;color:#002244;font-weight:bold;}.footer{text-align:center;font-size:12px;font-family:serif;margin:2em 0 0 0;}.dellist{font-weight:bold;text-align:center;}.delbuttons{text-align:center;padding-bottom:4px;}.managehead{background:#DDDDDD;color:#002244;padding:0px;}.postlists{background:#FFFFFF;width:100%;padding:0px;color:#800000;}.row1{background:#DDDDDD;color:#002244;}.row2{background:#CCCCCC;color:#002244;}.unkfunc{background:inherit;color:#789922;}.reflink{font-size:.8em;font-weight:bold;}.filesize{color:#666666;font-size:0.8em;margin:0 0 0 20px;text-decoration:none;}.filetitle{background:inherit;font-size:1.2em;color:#002244;font-weight:bold;}.postername{}.postertrip{color:#228854;}.oldpost,.notabene{color:#CC1105;font-weight:bold;}.omittedposts{color:#666666;}.reply{background:#DDDDDD;border:solid 1px #CCCCCC;padding:0;margin:0;border-radius:5px;-moz-border-radius:5px;-webkit-border-radius:5px;}blockquote{margin:.5em .5em .5em 1em;}.reply blockquote{margin:.5em;}.doubledash{display:none;vertical-align:top;clear:both;float:left;}.replytitle{font-size:1.2em;color:#002244;font-weight:bold;}.commentpostername{}.thumbnailmsg{font-size:.6em;color:#666666;}hr{border-style:solid none none none;border-width:1px;border-color:#BBBBBB;}table{border-style:none;}table td{border-style:none;}.nothumb{background-color:#FFFFFF;border-style:dotted;margin:.3em .5em;}.abbrev{color:#666666;}.highlight{background:#EEDACB;color:#333333;border:2px dashed #EE6600;}.extrafunctions{color:#008000;}dl.menu dt{background:#DDDDDD;border:solid 1px #CCCCCC;border-radius:5px;-moz-border-radius:5px;-webkit-border-radius:5px;margin-top:1em;padding-left:.5em;cursor:pointer;}dl.menu dd{margin-left:.5em;padding-left:.5em;border-left:solid 1px #CCCCCC;}dl.menu dd.hidden{display:none;}.u{text-decoration:underline;}.s{text-decoration:line-through;}.hide{filter:alpha(opacity=0);-moz-opacity:0;opacity:0;}.hide:hover{filter:alpha(opacity=60);-moz-opacity:0.6;opacity:0.6;}.o{text-decoration:overline;}"
    after_style=".reply{padding:5px; margin-bottom:10px;}.spoiler{background:#bbb;color:#bbb}.spoiler:hover{color:#000}"
    server.wfile.write(
"""<!doctype html>

<meta charset = "utf-8" />
<head>
<style>
{}
{}
{}
</style>
</head>
<title>{}</title>""".format(pre_style, style, after_style, escape(title))
    )


def connect_page(server):
    page_head(server, "Подключение")

    server.wfile.write(
"""<h1>Подключение</h1>

<p>Чтобы подключиться к API BitMessage, необходимо в файл "keys.dat" (<a href = "https://bitmessage.org/wiki/Keys.dat#Location">инструкция</a>, как его найти) к разделу "[bitmessagesettings]" добавить следующие строки:</p>

<pre>apienabled = true
apiinterface = 127.0.0.1
apiport = 8442
apiusername = ananas
apipassword = 123456</pre>

<p>Последние четыре параметра можно изменить, но тогда надо будет вводить их в форму ниже.</p>

<form method = "POST">
    <p><label>apiinterface = <input name = "interface" value = "127.0.0.1" /></label></p>

    <p><label>apiport = <input name = "port" value = "8442" /></label></p>

    <p><label>apiusername = <input name = "username" value = "ananas" /></label></p>

    <p><label>apipassword = <input name = "password" type = "password" value = "123456" /></label></p>

    <p><input type = "submit" value = "Подключиться" /></p>
</form>"""
        )

def index_page(server):
    page_head(server, "Bitaba")

    server.wfile.write(
"""

<h1>Доски</h1>

<ul>
"""
    )

    for i in api.get_boards():
        server.wfile.write(
""" <li><a href = "{}/">{}</a></li>
""".format(escape(i["address"], True), escape(i["label"]))
        )

    server.wfile.write(
"""</ul>
    
<p>Настроить доски можно через графический клиент. Для добавления/создания - меню "Файл", "Присоединиться или создать chan", галочка "Создать новый chan". Чтобы удалять/переименовывать, - вкладка "Ваши Адреса".</p>

<p>По-хорошему, надо добавить в веб-интерфейс возможность редактировать список досок и удалять сообщения, но это ёбырно.</p>"""
    )

def board_page(server, board):
    page_head(server, board)

    server.wfile.write(
"""

<h1>Треды</h1>

<ul>
"""
    )

    for i in api.get_threads(board):
        server.wfile.write(
""" <li>
    <h3>{}</h3>
    <a href = "{}/">Ответы: {}</a>
</li>
""".format(
                escape(i["subject"]) if i["subject"] else "<i>Без заголовка</i>",
                escape(i["ID"], True),
                i["replies"]
            )
        )

    server.wfile.write(
"""</ul>

<h2 style="color:#ff6600">Создать</h2>

<div class="postarea">
    <form method = "post" enctype = "multipart/form-data">
    

    <table cellspacing="2"><tbody>
    <tr>
        <td class="postblock">Заголовок</td>
        <td>
            <input name = "subject" /> <span style="font-size: x-small">(не должен начинаться с "Re: ".)</span>
        </td>
    </tr>
    <tr>
        <td class="postblock">Сообщение</td>
        <td>
            <textarea name="message" cols="60" rows="6"></textarea>
        </td>
    </tr>
    <tr>
        <td class="postblock">Картинка</td>
        <td>
            <input type="file" name="image" />
        </td>
    </tr>
    <tr>
        <td class="postblock"></td>
        <td>
            <input type="submit" value = "Создать" />
        </td>
    </tr>

    <input type = "hidden" name = "to" value = "{0}" />
    <input type = "hidden" name = "from" value = "{0}" />
</form>""".format(escape(board, True))
    )

import re
def mark_up(source):
    # Разметку бы сделать
    result = ""

    lines = source.split("\n")

    if len(lines) > 0:
        if (
            lines[-1][: 23] == "data:image/jpeg;base64," or
            lines[-1][: 22] == "data:image/png;base64," or
            lines[-1][: 22] == "data:image/gif;base64,"
        ):
            result += (
"""<img src = "{}" />
""".format(escape(lines[-1]))
            )

            lines.pop()
        elif lines[-1] == "":
            lines.pop()
    r = escape("\n".join(lines)).replace("\n", "<br />")
    r = re.sub(r"\[b\](.*?)\[\/b\]", r"<b>\1</b>", r)
    r = re.sub(r"\[i\](.*?)\[\/i\]", r"<i>\1</i>", r)
    r = re.sub(r"\[s\](.*?)\[\/s\]", r"<s>\1</s>", r)
    r = re.sub(r"\[%\](.*?)\[\/%\]", r"<span class='spoiler'>\1</span>", r)
    r = re.sub(r"\[spoiler\](.*?)\[\/spoiler\]", r"<span class='spoiler'>\1</span>", r)

    return result + "   {}".format(r)

def thread_page(server, board, ID):
    thread = api.get_threads(board, ID)

    if thread is not None:
        page_head(server, thread["subject"] + " - " + board)

        server.wfile.write(
"""

<h1>{}</h1>


""".format(escape(thread["subject"]))
        )

        for i in [thread["oppost"]] + thread["replies"]:
            server.wfile.write(
"""
<table><tbody><tr><td class="doubledash">&gt;&gt;</td>
<td style="min-width: 32em" class="reply" id="">
<a name=""></a>
<label><input type="checkbox" name="delete" value="" />
<span class="replytitle"></span>
<span class="commentpostername">{}</span>
{}</label>
<span class="reflink">
<a href="">{}</a>
</span>&nbsp;<br />
<blockquote>
{}
</blockquote>
</td></tr></tbody></table>
""".format(
                    # Надо бы выводить имя из адресной книги, если оно там есть

                    "Аноним" if i["poster"] == board else escape(i["poster"]),
                    str(datetime.fromtimestamp(float(i["date"]))),
                    escape(i["ID"]),
                    mark_up(i["message"])
                )
            )

        server.wfile.write(
"""

<h2 style="color:#ff6600">Ответить</h2>

<div class="postarea">
    <form method = "post" enctype = "multipart/form-data">
    

    <table cellspacing="2"><tbody>
    <tr>
        <td class="postblock">Сообщение</td>
        <td>
            <textarea name="message" cols="60" rows="6"></textarea>
        </td>
    </tr>
    <tr>
        <td class="postblock">Картинка</td>
        <td>
            <input type="file" name="image" />
        </td>
    </tr>

    <tr><td class="postblock"></td><td><input type="submit" value="Ответить" /></td></tr>

    <input type="hidden" name="subject" value = "{0}" />
    <input type="hidden" name="to" value = "{1}" />
    <input type="hidden" name="from" value = "{1}" />
</form>""".format(escape("Re: " + thread["subject"], True), escape(board, True))
        )
    else:
        server.send_error(404)

# Сервер

from BaseHTTPServer import HTTPServer, BaseHTTPRequestHandler
from urlparse import urlparse

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        path = urlparse(self.path).path.split("/")

        if api is None:
            connect_page(self)
        elif len(path) == 2 and path[1] == "":
            index_page(self)
        elif len(path) == 3 and path[1] != "" and path[2] == "":
            board_page(self, path[1])
        elif len(path) == 4 and path[1] != "" and path[2] != "" and path[3] == "":
            thread_page(self, path[1], path[2])
        else:
            self.send_error(404)

    def do_POST(self):
        path = urlparse(self.path).path.split("/")

        if api is None:
            connect_action(self)
        else:
            send_action(self)

HTTPServer(("127.0.0.1", 7890), Handler).serve_forever()