#!/usr/bin/env python3

from collections import OrderedDict
from ctypes import windll, create_unicode_buffer, memmove, c_byte

class Clipboard(object):

	def __init__(self):

		self.targets = {
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
			'CF_OEMTEXT': 7,
			'CF_OWNERDISPLAY': 0x0080,
			'CF_PALETTE': 9,
			'CF_PENDATA': 10,
			'CF_PRIVATEFIRST': 0x0200,
			'CF_PRIVATELAST': 0x02FF,
			'CF_RIFF': 11,
			'CF_SYLK': 4,
			'CF_TEXT': 1,
			'CF_TIFF': 6,
			'CF_UNICODETEXT': 13,
			'CF_WAVE': 12}
		self.names = {
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
		self.GMEM_MOVEABLE = 0x0002
		self.GMEM_ZEROINIT = 0x0040

	def get(self, targets):

		content = OrderedDict()
		targets_int = []
		target_name = create_unicode_buffer(1000)
		for target in targets:
			if target in self.targets:
				targets_int.append(self.targets[target])
			elif target == 'TARGETS':
				targets_int.append(target)
			else:
				targets_int.append(windll.user32.RegisterClipboardFormatW(target))
		windll.user32.OpenClipboard(None)
		for target in targets_int:
			if type(target) is int:
				if target in self.names:
					name = self.names[target]
				else:
					windll.user32.GetClipboardFormatNameW(
						target, target_name, 1000)
					name = target_name.value
				if windll.user32.IsClipboardFormatAvailable(target):
					handle = windll.user32.GetClipboardData(target)
					size = windll.kernel32.GlobalSize(handle)
					ptr = windll.kernel32.GlobalLock(handle)
					data = (c_byte * size)()
					memmove(data, ptr, size)
					windll.kernel32.GlobalUnlock(ptr)
					content[name] = bytes(data)
				else:
					content[name] = None
			else:
				formats = []
				format_ = windll.user32.EnumClipboardFormats(0)
				if format_:
					if format_ in self.names:
						formats.append(self.names[format_])
					else:
						windll.user32.GetClipboardFormatNameW(
							format_, target_name, 1000)
						formats.append(target_name.value)
				while format_:
					format_ = windll.user32.EnumClipboardFormats(format_)
					if format_:
						if format_ in self.names:
							formats.append(self.names[format_])
						else:
							windll.user32.GetClipboardFormatNameW(
								format_, target_name, 1000)
							formats.append(target_name.value)
				content[target] = formats
		windll.user32.CloseClipboard()
		return content

	def set(self, content):

		targets = OrderedDict()
		for target in content:
			if target in self.targets:
				targets[target] = self.targets[target]
			else:
				targets[target] = windll.user32.RegisterClipboardFormatW(target)
		windll.user32.OpenClipboard(None)
		windll.user32.EmptyClipboard()
		for target, data in content.items():
			if data:
				if type(data) is str:
					data = data.encode('utf-16le')
				handle = windll.kernel32.GlobalAlloc(
					self.GMEM_MOVEABLE | self.GMEM_ZEROINIT, len(data) + 2)
				ptr = windll.kernel32.GlobalLock(handle)
				memmove(ptr, data, len(data))
				windll.kernel32.GlobalUnlock(handle)
				windll.user32.SetClipboardData(targets[target], handle)
		windll.user32.CloseClipboard()

	def clear(self):

		windll.user32.OpenClipboard(None)
		windll.user32.EmptyClipboard()
		windll.user32.CloseClipboard()

	def wrap_html(self, html):

		footer = '<!--EndFragment-->\r\n</body>\r\n</html>'
		header = ('Version:0.9\r\nStartHTML:{0}\r\nEndHTML:{1}\r\n'
			+ 'StartFragment:{2}\r\nEndFragment:{3}\r\n<html><body>\r\n'
			+ '<!--StartFragment-->')
		padded_header = header.format(*['00000000'] * 4)
		wrapped_html = ((header.format(
			str(97).zfill(8),
			str(97 + len(html) + len(footer)).zfill(8),
			str(len(padded_header)).zfill(8),
			str(len(padded_header) + len(html)).zfill(8)))
			+ html
			+ footer)
		return wrapped_html.encode()
