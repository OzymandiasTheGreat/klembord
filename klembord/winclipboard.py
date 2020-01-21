#!/usr/bin/env python3

from collections import OrderedDict, ByteString
from ctypes import windll, create_unicode_buffer, memmove, c_uint, c_wchar
from ctypes import c_void_p, c_bool, c_int, c_byte


UNSUPPORTED = {
	'CF_BITMAP': 2,
	'CF_DIB': 8,
	'CF_DIBV5': 17,
	'CF_DIF': 5,
	'CF_DSPBITMAP': 0x0082,
	'CF_DSPENHMETAFILE': 0x008E,
	'CF_DSPMETAFILEPICT': 0x0083,
	'CF_DSPTEXT': 0x0081,
	'CF_ENHMETAFILE': 14,
	'CF_GDIOBJFIRST': 0x0300,
	'CF_GDIOBJLAST': 0x03FF,
	'CF_HDROP': 15,
	'CF_LOCALE': 16,
	'CF_METAFILEPICT': 3,
	'CF_OWNERDISPLAY': 0x0080,
	'CF_PALETTE': 9,
	'CF_PENDATA': 10,
	'CF_RIFF': 11,
	'CF_SYLK': 4,
	'CF_TIFF': 6,
	'CF_WAVE': 12}
TARGETS = {
	'CF_OEMTEXT': 7,
	'CF_PRIVATEFIRST': 0x0200,
	'CF_PRIVATELAST': 0x02FF,
	'CF_TEXT': 1,
	'CF_UNICODETEXT': 13}
NAMES = {
	1: 'CF_TEXT',
	2: 'CF_BITMAP',
	3: 'CF_METAFILEPICT',
	4: 'CF_SYLK',
	5: 'CF_DIF',
	6: 'CF_TIFF',
	7: 'CF_OEMTEXT',
	8: 'CF_DIB',
	9: 'CF_PALETTE',
	10: 'CF_PENDATA',
	11: 'CF_RIFF',
	12: 'CF_WAVE',
	13: 'CF_UNICODETEXT',
	14: 'CF_ENHMETAFILE',
	15: 'CF_HDROP',
	16: 'CF_LOCALE',
	17: 'CF_DIBV5',
	128: 'CF_OWNERDISPLAY',
	129: 'CF_DSPTEXT',
	130: 'CF_DSPBITMAP',
	131: 'CF_DSPMETAFILEPICT',
	142: 'CF_DSPENHMETAFILE',
	512: 'CF_PRIVATEFIRST',
	767: 'CF_PRIVATELAST',
	768: 'CF_GDIOBJFIRST',
	1023: 'CF_GDIOBJLAST'}
GMEM_MOVEABLE = 0x0002
GMEM_ZEROINIT = 0x0040


class WinClipboard(object):

	windll.user32.RegisterClipboardFormatW.argtypes = (c_wchar * 1024, )
	windll.user32.RegisterClipboardFormatW.restype = c_uint
	windll.user32.OpenClipboard.argtypes = (c_void_p, )
	windll.user32.OpenClipboard.restype = c_bool
	windll.user32.EnumClipboardFormats.argtypes = (c_uint, )
	windll.user32.EnumClipboardFormats.restype = c_uint
	windll.user32.GetClipboardFormatNameW.argtypes = (
		c_uint, c_wchar * 1024, c_int)
	windll.user32.GetClipboardFormatNameW.restype = c_int
	windll.user32.IsClipboardFormatAvailable.argtypes = (c_uint, )
	windll.user32.IsClipboardFormatAvailable.restype = c_bool
	windll.user32.GetClipboardData.argtypes = (c_uint, )
	windll.user32.GetClipboardData.restype = c_void_p
	windll.kernel32.GlobalSize.argtypes = (c_void_p, )
	windll.kernel32.GlobalSize.restype = c_uint
	windll.kernel32.GlobalLock.argtypes = (c_void_p, )
	windll.kernel32.GlobalLock.restype = c_void_p
	windll.kernel32.GlobalUnlock.argtypes = (c_void_p, )
	windll.kernel32.GlobalUnlock.restype = c_bool
	windll.user32.CloseClipboard.argtypes = ()
	windll.user32.CloseClipboard.restype = c_bool
	windll.user32.EmptyClipboard.argtypes = ()
	windll.user32.EmptyClipboard.restype = c_bool
	windll.kernel32.GlobalAlloc.argtypes = (c_uint, c_uint)
	windll.kernel32.GlobalAlloc.restype = c_void_p
	windll.user32.SetClipboardData.argtypes = (c_uint, c_void_p)
	windll.user32.SetClipboardData.restype = c_void_p

	def get(self, targets):

		content = OrderedDict()
		formats = {}
		for target in targets:
			if target == 'TARGETS':
				formats[target] = -1
			elif target in UNSUPPORTED:
				raise TypeError('Unsupported target/clipboard format')
			elif target in TARGETS:
				formats[target] = TARGETS[target]
			else:
				formats[target] = windll.user32.RegisterClipboardFormatW(
					create_unicode_buffer(target, 1024))
		if windll.user32.OpenClipboard(None):
			for target, format in formats.items():
				if format < 0:
					names = []
					next_format = windll.user32.EnumClipboardFormats(0)
					while next_format:
						if next_format in NAMES:
							names.append(NAMES[next_format])
						else:
							name = create_unicode_buffer(1024)
							if windll.user32.GetClipboardFormatNameW(
									next_format, name, 1024) > 0:
								names.append(name.value)
						next_format = windll.user32.EnumClipboardFormats(
							next_format)
					content[target] = tuple(names)
				else:
					if windll.user32.IsClipboardFormatAvailable(format):
						handle = windll.user32.GetClipboardData(format)
						size = windll.kernel32.GlobalSize(handle)
						ptr = windll.kernel32.GlobalLock(handle)
						data = (c_byte * size)()
						memmove(data, ptr, size)
						windll.kernel32.GlobalUnlock(ptr)
						content[target] = bytes(data)
					else:
						content[target] = None
			windll.user32.CloseClipboard()
		else:
			raise RuntimeError('Failed to open clipboard')
		return content

	def set(self, content):

		formats = OrderedDict()
		for target, data in content.items():
			if not isinstance(data, (str, ByteString, type(None))):
				raise TypeError('Unsupported data type:\n{}'.format(repr(data)))
			if target in UNSUPPORTED:
				raise TypeError('Unsupported target/clipboard format')
			elif data:
				if target in TARGETS:
					if isinstance(data, str):
						formats[TARGETS[target]] = data.encode()
					else:
						formats[TARGETS[target]] = data
				else:
					format = windll.user32.RegisterClipboardFormatW(
						create_unicode_buffer(target, 1024))
					if isinstance(data, str):
						formats[format] = data.encode()
					else:
						formats[format] = data
		if windll.user32.OpenClipboard(None):
			windll.user32.EmptyClipboard()
			for format, data in formats.items():
				handle = windll.kernel32.GlobalAlloc(
					GMEM_MOVEABLE | GMEM_ZEROINIT, len(data) + 2)
				ptr = windll.kernel32.GlobalLock(handle)
				memmove(ptr, data, len(data))
				windll.kernel32.GlobalUnlock(ptr)
				windll.user32.SetClipboardData(format, handle)
			windll.user32.CloseClipboard()
		else:
			raise RuntimeError('Failed to open clipboard')

	def clear(self):

		if windll.user32.OpenClipboard(None):
			windll.user32.EmptyClipboard()
			windll.user32.CloseClipboard()
		else:
			raise RuntimeError('Failed to open clipboard')

	def wrap_html(self, fragment_str):
		fragment_bytes = fragment_str.encode('utf8')
		footer = '<!--EndFragment-->\r\n</body>\r\n</html>'
		header = ('Version:0.9\r\nStartHTML:{0}\r\nEndHTML:{1}\r\n'
			+ 'StartFragment:{2}\r\nEndFragment:{3}\r\n<html><body>\r\n'
			+ '<!--StartFragment-->')
		padded_header = header.format(*['00000000'] * 4)
		wrapped = b''.join((
			header.format(
				str(97).zfill(8),
				str(97 + len(fragment_bytes) + len(footer)).zfill(8),
				str(len(padded_header)).zfill(8),
				str(len(padded_header) + len(fragment_bytes)).zfill(8))
				.encode('utf8'),
			fragment_bytes,
			footer.encode('utf8')))
		return wrapped
