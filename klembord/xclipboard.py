#!/usr/bin/env python3

import time
from threading import Thread
from queue import Queue, Empty
from collections import ByteString
from Xlib import X, display, Xatom
from Xlib.protocol import event


class XSelection(Thread):

	def __init__(self, selection='CLIPBOARD'):

		Thread.__init__(self, name='klembord XSelection', daemon=True)
		self.display = display.Display()
		self.SELECTION = self.display.get_atom(selection)
		self.TARGETS = self.display.get_atom('TARGETS')
		self.SAVE_TARGETS = self.display.get_atom('SAVE_TARGETS')
		self.CMANAGER_ATOM = self.display.get_atom('CLIPBOARD_MANAGER')
		self.ST_PROPERTY = self.display.get_atom('KLEMBORD_SELECTION')
		self.MULTIPLE = self.display.get_atom('MULTIPLE')
		self.save_targets = []
		self.getter_window = self.display.screen().root.create_window(
			0, 0, 1, 1, 0, X.CopyFromParent)
		self.getter_window.set_wm_name('klembord getter')
		self.inbox = Queue()
		self.setter_window = self.display.screen().root.create_window(
			0, 0, 1, 1, 0, X.CopyFromParent)
		self.setter_window.set_wm_name('klembord setter')
		self.outbox = Queue()
		self.requests = Queue()
		self.content_set = False
		self.selection_clear = event.SelectionClear(
			window=self.setter_window,
			atom=self.SELECTION,
			time=X.CurrentTime)
		self.setter = Thread(
			target=self.process_outgoing,
			name='klembord XSelection setter',
			daemon=True)
		self.setter.start()
		self.start()

	def run(self):

		while True:
			xevent = self.display.next_event()
			if (xevent.type == X.SelectionNotify
					and xevent.selection == self.SELECTION
					and xevent.requestor == self.getter_window):
				self.process_incoming(xevent)
			elif (xevent.type == X.SelectionRequest
					and xevent.owner == self.setter_window
					and xevent.selection == self.SELECTION):
				self.requests.put_nowait(xevent)
			elif (xevent.type == X.SelectionClear
					and xevent.window == self.setter_window
					and xevent.atom == self.SELECTION):
				self.requests.put_nowait(xevent)
			elif (xevent.type == X.SelectionNotify
					and xevent.selection == self.CMANAGER_ATOM
					and xevent.target == self.SAVE_TARGETS):
				self.requests.put_nowait(xevent)

	def process_incoming(self, xevent):

		try:
			target = self.display.get_atom_name(xevent.target)
			if target == 'TARGETS':
				target_atoms = self.getter_window.get_full_property(
					xevent.target, Xatom.ATOM).value
				data = []
				for atom in target_atoms:
					data.append(self.display.get_atom_name(atom))
				data = tuple(data)
			else:
				prop = self.getter_window.get_full_property(
					xevent.target, xevent.target)
				if prop:
					data = prop.value
					if isinstance(data, str):
						data = data.encode()
					else:
						data = bytes(data)
				else:
					data = None
			self.inbox.put_nowait((target, data))
		except Exception:
			self.process_incoming(xevent)

	def process_outgoing(self):

		def process_request(client, property, target):
			prop_set = True
			if property == X.NONE:
				client_prop = target
			else:
				client_prop = property
			if target == self.TARGETS:
				prop_value = [self.TARGETS, self.SAVE_TARGETS]
				prop_value += [target for target, data in content.items()
					if data]
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
				wanted_prop = client.get_full_property(
					client_prop, X.AnyPropertyType)
				if wanted_prop:
					wanted = [wanted_prop.value[i:i+2]
						for i in range(0, len(wanted_prop.value), 2)]
					for target, prop in wanted:
						process_request(client, prop, target)
					prop_set = False
				else:
					client_prop = X.NONE
			else:
				client_prop = X.NONE
			if client_prop != X.NONE and prop_set:
				client.change_property(
					client_prop, prop_type, prop_format, prop_value)
			return client_prop

		def serve():
			while True:
				xevent = self.requests.get()
				self.requests.task_done()
				if xevent.type == X.SelectionRequest:
					client_prop = process_request(
						xevent.requestor, xevent.property, xevent.target)
					selection_notify = event.SelectionNotify(
						time=xevent.time,
						requestor=xevent.requestor,
						selection=xevent.selection,
						target=xevent.target,
						property=client_prop)
					xevent.requestor.send_event(selection_notify)
					self.flushRetry()
				elif xevent.type == X.SelectionClear:
					while not self.requests.empty():
						try:
							self.requests.get_nowait()
							self.requests.task_done()
						except Empty:
							break
					self.content_set = False
					break
				elif xevent.type == X.SelectionNotify:
					if xevent.property == X.NONE:
						print(
							'Failed to transfer ownership to '
							+ 'Clipboard Manager')

		def take_ownership():
			self.setter_window.set_selection_owner(
				self.SELECTION, X.CurrentTime)
			self.flushRetry()

		while True:
			content = self.outbox.get()
			self.outbox.task_done()
			self.content_set = True
			take_ownership()
			current_owner = self.display.get_selection_owner(self.SELECTION)
			while current_owner != self.setter_window:
				take_ownership()
				time.sleep(0.005)
				current_owner = self.display.get_selection_owner(self.SELECTION)
			serve()

	def get(self, targets):

		content = {}
		now = time.monotonic()
		self.flushRetry()
		owner = self.display.get_selection_owner(self.SELECTION)
		if owner != X.NONE:
			for target in targets:
				target_atom = self.display.get_atom(target)
				selection_request = event.SelectionRequest(
					owner=owner,
					requestor=self.getter_window,
					selection=self.SELECTION,
					target=target_atom,
					property=target_atom,
					time=X.CurrentTime)
				owner.send_event(selection_request)
				self.flushRetry()
			while self.inbox.empty():
				if (time.monotonic() - now) >= 0.05:
					break
				time.sleep(0.005)
			now = time.monotonic()
			while not self.inbox.empty():
				if (time.monotonic() - now) >= 0.05:
					break
				target, data = self.inbox.get()
				content[target] = data
				self.inbox.task_done()
		for target in targets:
			if target not in content:
				content[target] = None
		return content

	def set(self, content):

		self.save_targets.clear()
		content_atoms = {}
		for target, data in content.items():
			if not isinstance(data, (str, ByteString, type(None))):
				raise TypeError('Unsupported data type:\n{}'.format(repr(data)))
			target_atom = self.display.get_atom(target)
			if data:
				self.save_targets.append(target_atom)
			content_atoms[target_atom] = data
		if self.content_set:
			self.setter_window.send_event(self.selection_clear)
			self.flushRetry()
		self.outbox.put_nowait(content_atoms)

	def store(self):

		if self.content_set:
			cmanager = self.display.get_selection_owner(self.CMANAGER_ATOM)
			if cmanager != X.NONE:
				self.setter_window.change_property(
					self.ST_PROPERTY, Xatom.ATOM, 32, self.save_targets)
				self.setter_window.convert_selection(
					self.CMANAGER_ATOM, self.SAVE_TARGETS, self.ST_PROPERTY,
					X.CurrentTime)
				self.flushRetry()
				self.save_targets.clear()

	def clear(self):

		self.save_targets.clear()
		self.content_set = True
		self.outbox.put_nowait({})
		self.setter_window.send_event(self.selection_clear)
		self.flushRetry()

	def flushRetry(self):
		try:
			self.display.flush()
		except Exception:
			self.flushRetry()
