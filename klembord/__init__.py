#!/usr/bin/env python3

"""A pure Python cross-platform package offering full Clipboard access.

Note:
	Windows standard binary formats such as 'CF_BITMAP' are not supported yet.
	These require more understanding of Windows API than I currently posses.

Attributes:
	__all__ (tuple): All objects and module-level functions offered by this
		package, except :func:`.set` because it conflicts with built-in
		:class:`set`.
	SELECTION (.Selection): Selection object used by module-level functions.
		You don't need to explicitely initialize it unless you're working with
		selection other than 'CLIPBOARD'.
"""

import sys
from collections import OrderedDict, Mapping, ByteString, Sequence
if sys.platform.startswith('win32'):
	from .winclipboard import WinClipboard
	WINDOWS = True
	LINUX = False
else:
	from .xclipboard import XSelection
	WINDOWS = False
	LINUX = True


__all__ = ('Selection', 'get', 'set_text', 'get_text', 'set_with_rich_text',
	'get_with_rich_text', 'clear', 'store', 'wrap_html', 'init')


W_UNICODE = 'CF_UNICODETEXT'
W_HTML = 'HTML Format'
L_TEXT = 'STRING'
L_UNICODE = 'UTF8_STRING'
L_HTML = 'text/html'
ASCII = 'ascii'
UTF8 = 'utf8'
UTF16 = 'utf-16le'


SELECTION = None


class Selection(object):
	"""A selection object.

	By default and on Windows this object represents clipboard.
	On Linux other selections are also supported.

	Attributes:
		selection (str): The selection this object represents.
	"""

	def __init__(self, selection='CLIPBOARD'):
		"""Initialize selection (clipboard).

		Args:
			selection (str): Selection to init. Can be 'CLIPBOARD' (default),
				'PRIMARY' or 'SECONDARY'.
				Note:
					On Windows selection defaults to 'CLIPBOARD' and this
					argument is ignored.
		"""

		if WINDOWS:
			self.selection = 'CLIPBOARD'
			self._interface = WinClipboard()
		else:
			self.selection = selection
			self._interface = XSelection(selection=selection)

	def set(self, content):
		"""Set selection contents to content.

		Args:
			content (Mapping): A mapping where key is format/target and value
				is data to set this format/target to. Value can be
				:class:`str`, :class:`ByteString` or :obj:`None`.
		"""

		if isinstance(content, Mapping):
			self._interface.set(content)
		else:
			raise TypeError('content is not a Mapping')

	def get(self, targets):
		"""Get the contents of specified formats/targets.

		To get the list of available formats/targets include a special target
		'TARGETS'.

		Args:
			targets (Sequence): A sequence of strings specifying which
				formats/targets to get.
		Returns:
			Mapping: A mapping where key is specified format/target
				and value is bytes object representing the data.
				If targets included 'TARGETS', it's value will be a tuple of
				strings representing available formats/targets.
				On Linux :class:`dict` is used, on Windows :class:`OrderedDict`
				is used instead.
		"""

		if isinstance(targets, Sequence):
			return self._interface.get(targets)
		else:
			raise TypeError('targets is not a Sequence')

	def set_text(self, text):
		"""Set the plaintext formats/targets to text.

		Args:
			text (str): Text to set selection to.
		"""

		if isinstance(text, (str, type(None))):
			if WINDOWS:
				if text:
					text = text.encode(UTF16)
				else:
					text = ''.encode(UTF16)
				self.set({W_UNICODE: text})
			else:
				if text:
					string = text.encode(ASCII, 'ignore')
					text = text.encode(UTF8)
				else:
					string = ''.encode(ASCII, 'ignore')
					text = ''.encode(UTF8)
				self.set({L_TEXT: string, L_UNICODE: text})
		else:
			raise TypeError('text is not a str')

	def get_text(self):
		"""Get the contents of selection as plaintext.

		Returns:
			str: The text contained in selection or :obj:`None`.
		"""

		if WINDOWS:
			content = self.get((W_UNICODE, ))
			data = content[W_UNICODE]
			if data:
				return data.decode(UTF16)
			else:
				return data
		else:
			content = self.get((L_TEXT, L_UNICODE))
			data = content[L_UNICODE]
			if data:
				try:
					return data.decode(UTF8)
				except UnicodeDecodeError:
					return None
			else:
				data = content[L_TEXT]
				if data:
					return data.decode(ASCII, 'ignore')
				else:
					return None

	def set_with_rich_text(self, text, html):
		"""Set the plaintext and html rich text formats/targets to text and
		html respectively.

		Note:
			html should not include <html> and <body> tags. These are ignored
			on Linux and set automatically by :meth:`wrap_html` on Windows.

		Args:
			text (str): Plain text to set selection to.
			html (str): HTML formatted rich text to set selection to.
		"""

		if (isinstance(text, (str, type(None)))
				and isinstance(html, (str, type(None)))):
			content = []
			if WINDOWS:
				if html:
					html = self._interface.wrap_html(html)
					content.append((W_HTML, html))
				if text:
					text = text.encode(UTF16)
					content.append((W_UNICODE, text))
			else:
				if text:
					string = text.encode(ASCII, 'ignore')
					content.append((L_TEXT, string))
					text = text.encode(UTF8)
					content.append((L_UNICODE, text))
				if html:
					html = html.encode(UTF8)
					content.append((L_HTML, html))
			self.set(OrderedDict(content))
		else:
			raise TypeError('text or html is not str')

	def get_with_rich_text(self):
		"""Get the contents of the selection in plaintext and HTML formats.

		Returns:
			tuple: A tuple where first member is the plaintext string (str)
				and the second member HTML fragment (str) representing
				selection contents.
		"""

		if WINDOWS:
			content = self.get((W_HTML, W_UNICODE))
			html = content[W_HTML]
			if html:
				# Strip HTML Format additions and return just the fragment.
				html = html.decode(UTF8)[131:-38]
			text = content[W_UNICODE]
			if text:
				text = text.decode(UTF16)
		else:
			content = self.get((L_TEXT, L_UNICODE, L_HTML))
			text = content[L_UNICODE]
			if text:
				text = text.decode(UTF8)
			else:
				text = content[L_TEXT]
				if text:
					text = text.decode(ASCII, 'ignore')
			html = content[L_HTML]
			if html:
				try:
					html = html.decode(UTF8)
				except UnicodeDecodeError:
					try:
						html = html.decode(UTF16)
					except UnicodeDecodeError:
						html = html.decode(UTF8, 'ignore')
		return (text, html)

	def clear(self):
		"""Empty selection.
		"""

		self._interface.clear()

	def store(self):
		"""Store selection contents so they're available after script exits.

		Note:
			This method is Linux only and only works for 'CLIPBOARD' selection.
			On Windows it raises :exc:`AttributeError`.
		"""

		self._interface.store()

	def wrap_html(self, fragment):
		"""Wrap HTML fragment so it complies with 'HTML Format' spec.

		Note:
			This method is Windows only and raises :exc:`AttributeError`
			on Linux.
		Args:
			fragment (str): HTML fragment w/o <html> and <body> tags.
		Returns:
			bytes: The wrapped fragment, encoded in UTF-8.
		"""

		return self._interface.wrap_html(fragment)


def init(selection='CLIPBOARD'):
	"""Initialize module-level selection object with a given selection.

	Args:
		selection (str): Selection to init. Valid selections are 'CLIPBOARD'
			(default), 'PRIMARY' and 'SECONDARY'. On Windows this argument
			is ignored.
	"""

	global SELECTION
	SELECTION = Selection(selection=selection)


def set(content):
	"""Set selection contents to content.

	Args:
		content (Mapping): A mapping where key is format/target and value
			is data to set this format/target to. Value can be
			:class:`str`, :class:`ByteString` or :obj:`None`.
	"""

	global SELECTION
	if SELECTION is None:
		SELECTION = Selection()
	SELECTION.set(content)


def get(targets):
	"""Get the contents of specified formats/targets.

	To get the list of available formats/targets include a special target
	'TARGETS'.

	Args:
		targets (Sequence): A sequence of strings specifying which
			formats/targets to get.
	Returns:
		Mapping: A mapping where key is specified format/target
			and value is bytes object representing the data.
			If targets included 'TARGETS', it's value will be a tuple of
			strings representing available formats/targets.
			On Linux :class:`dict` is used, on Windows :class:`OrderedDict`
			is used instead.
	"""

	global SELECTION
	if SELECTION is None:
		SELECTION = Selection()
	return SELECTION.get(targets)


def set_text(text):
	"""Set the plaintext formats/targets to text.

	Args:
		text (str): Text to set selection to.
	"""

	global SELECTION
	if SELECTION is None:
		SELECTION = Selection()
	SELECTION.set_text(text)


def get_text():
	"""Get the contents of selection as plaintext.

	Returns:
		str: The text contained in selection or :obj:`None`.
	"""

	global SELECTION
	if SELECTION is None:
		SELECTION = Selection()
	return SELECTION.get_text()


def set_with_rich_text(text, html):
	"""Set the plaintext and html rich text formats/targets to text and
	html respectively.

	Note:
		html should not include <html> and <body> tags. These are ignored
		on Linux and set automatically by :meth:`wrap_html` on Windows.

	Args:
		text (str): Plain text to set selection to.
		html (str): HTML formatted rich text to set selection to.
	"""

	global SELECTION
	if SELECTION is None:
		SELECTION = Selection()
	SELECTION.set_with_rich_text(text, html)


def get_with_rich_text():
	"""Get the contents of the selection in plaintext and HTML formats.

	Returns:
		tuple: A tuple where first member is the plaintext string (str)
			and the second member HTML fragment (str) representing
			selection contents.
	"""

	global SELECTION
	if SELECTION is None:
		SELECTION = Selection()
	return SELECTION.get_with_rich_text()


def clear():
	"""Empty selection.
	"""

	global SELECTION
	if SELECTION is None:
		SELECTION = Selection()
	SELECTION.clear()


def store():
	"""Store selection contents so they're available after script exits.

	Note:
		This method is Linux only and only works for 'CLIPBOARD' selection.
		On Windows it raises :exc:`AttributeError`.
	"""

	global SELECTION
	if SELECTION is None:
		SELECTION = Selection()
	SELECTION.store()


def wrap_html(fragment):
	"""Wrap HTML fragment so it complies with 'HTML Format' spec.

	Note:
		This method is Windows only and raises :exc:`AttributeError`
		on Linux.
	Args:
		fragment (str): HTML fragment w/o <html> and <body> tags.
	Returns:
		bytes: The wrapped fragment, encoded in UTF-8.
	"""

	global SELECTION
	if SELECTION is None:
		SELECTION = Selection()
	return SELECTION.wrap_html(fragment)
