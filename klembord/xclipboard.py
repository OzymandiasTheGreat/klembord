#!/usr/bin/env python3

import time
import sys
from threading import Thread
from queue import Queue, Empty
from collections import ByteString
from traceback import print_exception
from Xlib import X, display, Xatom
from Xlib.protocol import event
from Xlib.error import CatchError, BadAtom
from stopit import ThreadingTimeout


errHandler = CatchError()


class ErrorReporter(object):
	debug = False

	@classmethod
	def print(cls, error):
		if cls.debug:
			print_exception(error.__class__, error, error.__traceback__)


class BrokenConnection(Exception):
	pass


class XGetter(Thread):

	def __init__(self, selection='CLIPBOARD'):
		super().__init__(name='klembord XGetter', daemon=True)
		self.selection = selection
		self._break = False
		self.inbox = Queue()
		self.initX()
		self.start()

	def initX(self):
		self.display = display.Display()

		# ATOMS
		self.SELECTION = self.display.intern_atom(self.selection)

		self.window = self.display.screen().root.create_window(
			0, 0, 1, 1, 0, X.CopyFromParent
		)
		self.window.set_wm_name('klembord XGetter window')

	def killX(self):
		self.window.destroy()
		self.display.close()

	def processEvent(self, xevent):
		try:
			target = self.display.get_atom_name(xevent.target)
		except BadAtom as e:
			ErrorReporter.print(e)
			return
		if target == 'TARGETS':
			try:
				target_atoms = self.window.get_full_property(
					xevent.target, Xatom.ATOM
				).value
			except Exception as e:
				ErrorReporter.print(e)
				return
			data = []
			for atom in target_atoms:
				try:
					data.append(self.display.get_atom_name(atom))
				except BadAtom as e:
					ErrorReporter.print(e)
			data = tuple(data)
		else:
			try:
				prop = self.window.get_full_property(
					xevent.target, xevent.target
				)
			except Exception as e:
				ErrorReporter.print(e)
				return
			if prop:
				data = prop.value
				if isinstance(data, str):
					data = data.encode()
				else:
					data = bytes(data)
			else:
				data = None
		self.inbox.put_nowait((target, data))

	def run(self):
		while True:
			if self._break:
				self.killX()
				break
			if self.display.pending_events():
				xevent = self.display.next_event()
				if (
					xevent.type == X.SelectionNotify
					and xevent.selection == self.SELECTION
					and xevent.requestor == self.window
				):
					self.processEvent(xevent)
			time.sleep(0.005)

	def get(self, targets):
		content = {}
		try:
			self.display.flush()
		except Exception as e:
			ErrorReporter.print(e)
			raise BrokenConnection('Flushing events failed') from e
		try:
			owner = self.display.get_selection_owner(self.SELECTION)
		except BadAtom as e:
			ErrorReporter.print(e)
			raise BrokenConnection('Bad selection atom') from e
		if owner != X.NONE:
			for target in targets:
				target_atom = self.display.intern_atom(target)
				selection_request = event.SelectionRequest(
					owner=owner,
					requestor=self.window,
					selection=self.SELECTION,
					target=target_atom,
					property=target_atom,
					time=X.CurrentTime,
				)
				owner.send_event(selection_request, onerror=errHandler)
				try:
					self.display.flush()
				except Exception as e:
					ErrorReporter.print(e)
					raise BrokenConnection('Flushing events failed') from e
				if errHandler.get_error():
					raise BrokenConnection('Sending event failed')
			now = time.monotonic()
			while self.inbox.empty():
				if (time.monotonic() - now) >= 0.05:
					break
				time.sleep(0.005)
			now = time.monotonic()
			while not self.inbox.empty():
				if (time.monotonic() - now) >= 0.05:
					break
				try:
					target, data = self.inbox.get_nowait()
					self.inbox.task_done()
				except Empty:
					break
				content[target] = data
		for target in targets:
			if target not in content:
				content[target] = None
		return content

	def exit(self):
		self._break = True
		# self.join()
		time.sleep(0.005)


class XSetter(Thread):

	def __init__(self, selection='CLIPBOARD', reset=None):
		super().__init__(name='klembord XSetter', daemon=True)
		self.selection = selection
		self.reset = reset
		self._break = False
		self.save_targets = []
		self.outbox = Queue()
		self.requests = Queue()
		self.content_set = False
		self.initX()
		self.eventLoop = Thread(
			target=self.processEvents,
			name='klembord XSetter event loop',
			daemon=True,
		)
		self.start()
		self.eventLoop.start()

	def initX(self):
		self.display = display.Display()

		# ATOMS
		self.SELECTION = self.display.intern_atom(self.selection)
		self.TARGETS = self.display.intern_atom('TARGETS')
		self.SAVE_TARGETS = self.display.intern_atom('SAVE_TARGETS')
		self.CLIPBOARD_MANAGER = self.display.intern_atom('CLIPBOARD_MANAGER')
		self.ST_PROPERTY = self.display.intern_atom('KLEMBORD_SELECTION')
		self.MULTIPLE = self.display.intern_atom('MULTIPLE')

		self.window = self.display.screen().root.create_window(
			0, 0, 1, 1, 0, X.CopyFromParent
		)
		self.window.set_wm_name('klembord XSetter')

		self.selection_clear = event.SelectionClear(
			window=self.window,
			atom=self.SELECTION,
			time=X.CurrentTime,
		)

	def killX(self):
		self.window.destroy()
		self.display.close()

	def run(self):
		def serve():
			while True:
				xevent = self.requests.get()
				self.requests.task_done()
				if xevent is None:
					break
				elif xevent.type == X.SelectionRequest:
					client_prop = process_request(
						xevent.requestor,
						xevent.property,
						xevent.target
					)
					selection_notify = event.SelectionNotify(
						time=xevent.time,
						requestor=xevent.requestor,
						selection=xevent.selection,
						target=xevent.target,
						property=client_prop,
					)
					xevent.requestor.send_event(
						selection_notify, onerror=errHandler
					)
					try:
						self.display.flush()
					except Exception as e:
						ErrorReporter.print(e)
						self.reset()
						break
				elif xevent.type == X.SelectionClear:
					while not self.requests.empty():
						try:
							self.requests.get_nowait()
							self.requests.task_done()
						except Empty:
							break
					self.content_set = False
					break
				elif xevent.type == X.SelectionNotify and xevent.property == X.NONE:
					print(
						'Failed to transfer ownership to Clipboard Manager',
						file=sys.stderr
					)
					break

		def process_request(client, property, target):
			prop_set = True
			if property == X.NONE:
				client_prop = target
			else:
				client_prop = property
			if target == self.TARGETS:
				prop_value = [self.TARGETS, self.SAVE_TARGETS]
				prop_value += [t for t, data in content.items() if data]
				prop_type = Xatom.ATOM
				prop_format = 32
			elif target in content:
				data = content[target]
				if isinstance(data, str):
					prop_value = data.encode()
				elif isinstance(data, ByteString):
					prop_value = data
				else:
					client_prop = X.NONE
				prop_type = target
				prop_format = 8
			elif target == self.MULTIPLE:
				try:
					wanted_prop = client.get_full_property(
						client_prop, X.AnyPropertyType
					)
				except Exception as e:
					ErrorReporter.print(e)
					self.reset()
					return
				if wanted_prop:
					wanted = [
						wanted_prop.value[i:i + 2]
							for i in range(0, len(wanted_prop.value), 2)
					]
					for target, prop in wanted:
						process_request(client, prop, target)
					prop_set = False
				else:
					client_prop = X.NONE
			else:
				client_prop = X.NONE
			if client_prop != X.NONE and prop_set:
				client.change_property(
					client_prop,
					prop_type,
					prop_format,
					prop_value,
					onerror=errHandler,
				)
				try:
					self.display.flush()
				except Exception as e:
					ErrorReporter.print(e)
					self.reset()
					return
				if errHandler.get_error():
					self.reset()
					return
			return client_prop

		while True:
			content = self.outbox.get()
			self.outbox.task_done()
			if content is None:
				break
			self.content_set = True
			self.window.set_selection_owner(
				self.SELECTION,
				X.CurrentTime,
				onerror=errHandler
			)
			try:
				self.display.flush()
			except Exception as e:
				ErrorReporter.print(e)
				self.reset()
				break
			if errHandler.get_error():
				self.reset()
				break
			try:
				current_owner = self.display.get_selection_owner(self.SELECTION)
			except (BadAtom, RuntimeError, TypeError) as e:
				ErrorReporter.print(e)
				self.reset()
				break
			if current_owner == self.window:
				server = Thread(
					target=serve, name='klembord XSetter server', daemon=True
				)
				server.start()

	def processEvents(self):
		while True:
			if self._break:
				self.killX()
				break
			try:
				if self.display.pending_events():
					xevent = self.display.next_event()
					if (
						xevent.type == X.SelectionRequest
						and xevent.owner == self.window
						and xevent.selection == self.SELECTION
					):
						self.requests.put_nowait(xevent)
					elif (
						xevent.type == X.SelectionClear
						and xevent.window == self.window
						and xevent.atom == self.SELECTION
					):
						self.requests.put_nowait(xevent)
					elif (
						xevent.type == X.SelectionNotify
						and xevent.selection == self.CLIPBOARD_MANAGER
						and xevent.target == self.SAVE_TARGETS
					):
						self.requests.put_nowait(xevent)
				time.sleep(0.005)
			except Exception as e:
				ErrorReporter.print(e)
				self.reset()
				break

	def set(self, content):
		self.save_targets.clear()
		content_atoms = {}
		for target, data in content.items():
			if not isinstance(data, (str, ByteString, type(None))):
				raise TypeError('Unsupported data type:\n{}'.format(repr(data)))
			with ThreadingTimeout(0.05) as timeout:
				try:
					target_atom = self.display.intern_atom(target)
				except RuntimeError as e:
					ErrorReporter.print(e)
					raise BrokenConnection('Failed to intern atom') from e
			if timeout.state == timeout.TIMED_OUT:
				raise BrokenConnection('Interning atoms timed out')
			if data:
				self.save_targets.append(target_atom)
			content_atoms[target_atom] = data
		if self.content_set:
			with ThreadingTimeout(0.05) as timeout:
				self.window.send_event(self.selection_clear, onerror=errHandler)
				try:
					self.display.flush()
				except Exception as e:
					ErrorReporter.print(e)
					raise BrokenConnection('Failed to flush events') from e
				if errHandler.get_error():
					raise BrokenConnection('Failed to send events')
			if timeout.state == timeout.TIMED_OUT:
				raise BrokenConnection('Sending event timed out')
		self.outbox.put_nowait(content_atoms)

	def store(self):
		if self.content_set:
			try:
				clipboardManager = self.display.get_selection_owner(
					self.CLIPBOARD_MANAGER
				)
			except BadAtom as e:
				ErrorReporter.print(e)
				raise BrokenConnection('Broken Clipboard Manager atom') from e
			if clipboardManager != X.NONE:
				self.window.change_property(
					self.ST_PROPERTY,
					Xatom.ATOM,
					32,
					self.save_targets,
					onerror=errHandler,
				)
				try:
					self.display.flush()
				except Exception as e:
					ErrorReporter.print(e)
					raise BrokenConnection('Failed to flush events') from e
				if errHandler.get_error():
					raise BrokenConnection('Failed to change window property')
				self.window.convert_selection(
					self.CLIPBOARD_MANAGER,
					self.SAVE_TARGETS,
					self.ST_PROPERTY,
					X.CurrentTime,
					onerror=errHandler,
				)
				try:
					self.display.flush()
				except Exception as e:
					ErrorReporter.print(e)
					raise BrokenConnection('Failed to flush events') from e
				if errHandler.get_error():
					raise BrokenConnection('Failed to convert selection')
				self.save_targets.clear()

	def clear(self):
		self.save_targets.clear()
		self.content_set = True
		self.outbox.put_nowait({})
		self.window.send_event(self.selection_clear, onerror=errHandler)
		try:
			self.display.flush()
		except Exception as e:
			ErrorReporter.print(e)
			raise BrokenConnection('Failed to flush events') from e
		if errHandler.get_error():
			raise BrokenConnection('Failed to send events')

	def exit(self):
		self._break = True
		self.outbox.put_nowait(None)
		self.requests.put_nowait(None)
		# self.join()
		# self.eventLoop.join()
		time.sleep(0.005)


class XSelection(object):

	def __init__(self, selection='CLIPBOARD'):
		self.selection = selection
		self.getter = XGetter(selection=selection)
		self.setter = XSetter(selection=selection, reset=self.resetSetter)
		self.lastContent = None

	def resetSetter(self):
		self.setter.exit()
		self.setter = XSetter(selection=self.selection, reset=self.resetSetter)
		if self.lastContent:
			self.set(self.lastContent)

	def get(self, targets):
		try:
			return self.getter.get(targets)
		except BrokenConnection:
			self.getter.exit()
			self.getter = XGetter(selection=self.selection)
			return self.get(targets)

	def set(self, content):
		try:
			self.setter.set(content)
		except BrokenConnection:
			self.resetSetter()

	def store(self):
		try:
			self.setter.store()
		except BrokenConnection:
			self.resetSetter()
			self.store()

	def clear(self):
		try:
			self.setter.clear()
		except BrokenConnection as e:
			ErrorReporter.print(e)
			self.resetSetter()
			self.clear()
