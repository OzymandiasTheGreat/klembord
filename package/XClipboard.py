#!/usr/bin/env python3

import time
from threading import Thread, Event
from queue import Queue
from Xlib import X, display, Xatom
from Xlib.protocol import event


class Clipboard(Thread):

	def __init__(self, selection='CLIPBOARD'):

		Thread.__init__(self, name='XClipboard', daemon=True)
		self.outbox = Queue()
		self.inbox = Queue()
		self.display = display.Display()
		self.window = self.display.screen().root.create_window(
			0, 0, 1, 1, 0, X.CopyFromParent)
		self.window.set_wm_name('klembord')
		self.selection = self.display.get_atom(selection)
		self.TARGETS = self.display.get_atom('TARGETS')
		self.selection_clear = event.SelectionClear(
			window=self.window,
			atom=self.selection,
			time=X.CurrentTime)
		self.current = {}
		self._content_change = Event()
		self._content_set = False

	def run(self):

		def run():

			while True:
				content = self.outbox.get()
				self.outbox.task_done()
				if content is None:
					break
				elif type(content) is dict:
					self.window.set_selection_owner(self.selection, X.CurrentTime)
					if (self.display.get_selection_owner(self.selection)
						== self.window):

						while True:
							xevent = self.display.next_event()

							if (xevent.type == X.SelectionRequest
								and xevent.owner == self.window
								and xevent.selection == self.selection):

								client = xevent.requestor
								if xevent.property == X.NONE:
									client_prop = xevent.target
								else:
									client_prop = xevent.property

								target_name = self.display.get_atom_name(
									xevent.target)
								if xevent.target == self.TARGETS:
									prop_value = ([self.TARGETS]
										+ [self.display.get_atom(target)
											for target in content
												if content[target]])
									prop_type = Xatom.ATOM
									prop_format = 32
								elif target_name in content:
									data = content[target_name]
									if type(data) is str:
										prop_value = data.encode()
									elif type(data) in {bytes, bytearray}:
										prop_value = data
									else:
										prop_value = b'\x00'
									prop_type = xevent.target
									prop_format = 8
								else:
									client_prop = X.NONE

								if client_prop != X.NONE:
									client.change_property(
										client_prop,
										prop_type,
										prop_format,
										prop_value)
								selection_notify = event.SelectionNotify(
									time=xevent.time,
									requestor=xevent.requestor,
									selection=xevent.selection,
									target=xevent.target,
									property=client_prop)
								client.send_event(selection_notify)

							elif (xevent.type == X.SelectionClear
								and xevent.window == self.window
								and xevent.atom == self.selection):

								self._content_set = False
								self._content_change.set()
								break

				else:
					xevent = self.display.next_event()
					if (xevent.type == X.SelectionNotify
						and xevent.selection == self.selection
						and xevent.requestor == self.window):

						target = self.display.get_atom_name(xevent.target)
						if target == 'TARGETS':
							targets = self.window.get_full_property(
								xevent.target, Xatom.ATOM).value
							data = []
							for atom in targets:
								data.append(self.display.get_atom_name(atom))
						else:
							prop = self.window.get_full_property(
								xevent.target, xevent.target)
							if prop:
								data = prop.value
							else:
								data = None
						self.inbox.put_nowait((target, data))

		while True:
			try:
				run()
			except RuntimeError:
				pass

	def set(self, content):

		if self._content_set:
			self.window.send_event(self.selection_clear)
			self.display.flush()
			self._content_change.wait()
		self.outbox.put_nowait(content)
		self.current = content
		self._content_set = True
		self._content_change.clear()

	def stop(self):

		self.outbox.put(None)

	def clear(self):

		self.set({})

	def get(self, targets):

		def set_owner():

			nonlocal owner
			owner = self.display.get_selection_owner(self.selection)

		def timer(func):

			start = time.perf_counter()
			func()
			return time.perf_counter() - start

		timeout = 0.01
		wait = 0.005
		counter = 0
		owner = X.NONE
		counter += timer(set_owner)
		while ((owner == X.NONE or (owner == self.window and not self.current))
			and counter < timeout):
			time.sleep(wait)
			counter += timer(set_owner)
			counter += wait
		if owner != self.window and owner != X.NONE:
			for target in targets:
				target_atom = self.display.get_atom(target)
				selection_request = event.SelectionRequest(
					owner=owner,
					requestor=self.window,
					selection=self.selection,
					target=target_atom,
					property=target_atom,
					time=X.CurrentTime)
				owner.send_event(selection_request)
				self.outbox.put_nowait(target)
			while self.inbox.empty() and counter < timeout:
				time.sleep(wait)
				counter += wait
			content = {}
			while not self.inbox.empty():
				target = self.inbox.get()
				content[target[0]] = target[1]
				self.inbox.task_done()
		elif owner == self.window:
			content = {}
			for target in targets:
				if target in self.current:
					content[target] = self.current[target]
		else:
			content = {}
		for target in targets:
			if target not in content:
				content[target] = None
		return content
