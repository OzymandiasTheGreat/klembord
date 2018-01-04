#!/usr/bin/env python3

import sys
from collections import OrderedDict
if sys.platform.startswith('linux'):
	from . import XClipboard
	LINUX = True
elif sys.platform.startswith('win32'):
	from . import WinClipboard
	LINUX = False

L_UNICODE = 'UTF8_STRING'
L_HTML = 'text/html'
W_UNICODE = 'CF_UNICODETEXT'
W_HTML = 'HTML Format'
UTF16 = 'utf-16le'

def init(selection='CLIPBOARD'):

	global clipboard
	if LINUX:
		clipboard = XClipboard.Clipboard(selection=selection)
		clipboard.start()
	else:
		clipboard = WinClipboard.Clipboard()

def set(content):

	clipboard.set(content)

def get(targets):

	return clipboard.get(targets)

def clear():

	clipboard.clear()

def set_text(text):

	if LINUX:
		clipboard.set({L_UNICODE: text})
	else:
		clipboard.set({W_UNICODE: text.encode(UTF16)})

def get_text():

	if LINUX:
		data = clipboard.get([L_UNICODE])
		return data[L_UNICODE].decode()
	else:
		data = clipboard.get([W_UNICODE])
		return data[W_UNICODE].decode(UTF16)

def set_with_rich_text(text, html):

	if LINUX:
		content = {L_UNICODE: text,  L_HTML: html}
		clipboard.set(content)
	else:
		content = OrderedDict(
			((W_HTML, clipboard.wrap_html(html)),
			(W_UNICODE, text.encode(UTF16))))
		clipboard.set(content)

def get_with_rich_text():

	if LINUX:
		data = clipboard.get([L_UNICODE, L_HTML])
		text = data[L_UNICODE]
		if text:
			text = text.decode()
		html = data[L_HTML]
		if html:
			html = html.decode()
		return (text, html)
	else:
		data = clipboard.get([W_UNICODE, W_HTML])
		html = data[W_HTML].decode() # Strip windows weirdness
		return (data[W_UNICODE].decode(UTF16), html)

def wrap_html(html):

	if LINUX:
		raise NotImplementedError('This function is only available on Win32')
	else:
		return clipboard.wrap_html(html)
