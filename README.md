# klembord

`klembord` is a python 3 package that provides full clipboard access on supported platforms (Linux and Windows for now, though this may change in the future).
`klembord` has minimal dependencies, depending only on platform specific apis, which means it can be used with any graphics toolkit or without a toolkit at all.

## Install and dependencies

`klembord` uses `python-xlib` under Linux and `ctypes` on Windows.
When installing with `pip` dependencies will be taken care of automatically.

`pip install klembord`

That's it!

## Usage

```python
>>> import klembord
>>> klembord.init()
>>> klembord.get_text()
'example clipboard text'
>>>klembord.set_text('some string')
```

`klembord` also includes convenience functions for working with rich text:

```python
>>> klembord.get_with_rich_text()
('example html', '<i>example html</i>')
>>> klembord.set_with_rich_text('plain text', '<b>plain text</b>')
```

Rich text function set platform's unicode and html formats.

On Linux accessing selections other than `CLIPBOARD` is easy, just pass selection name to `init`:

```python
klembord.init('PRIMARY')
```

If you need access to other targets/formats you can use `get` and `set` functions:

```python
>>> content = {'UTF8_STRING': 'string'.encode(), 'text/html': '<s>string</s>'.encode()}
>>> klembord.set(content)
>>> klembord.get(['UTF8_STRING', 'text/html', 'application/rtf'])
{'UTF8_STRING': b'string', 'text/html': b'<s>string</s>', 'application/rtf': None}

>>> from collections import OrderedDict
>>> content = OrderedDict()
>>> content['HTML Format'] = klembord.wrap_html('<a href="example.com">Example</a>')
>>> content['CF_UNICODETEXT'] = 'Example'.encode('utf-16le')
>>> klembord.set(content)
>>> klembord.get(['HTML Format', 'CF_RTF'])
{'HTML Format': b'<a href="example.com">Example</a>', 'CF_RTF': None}
```

These examples show manual way of setting clipboard with rich text.
Unlike convenience functions `get` and `set` takes dicts of bytes as arguments.
Key should be target/format string and value binary data or encoded string. Every given format/target will be set.

The first example is Linux usage. Most targets are encoded with `utf8` and it's all fairly simple.
The second shows usage on Windows. Now windows retrieves formats in order they were defined, so using `collections.OrderedDict` is a good idea to ensure that say html format takes precedence over plain text.
`CF_UNICODE`, the unicode text format is always encoded in `utf-16le`.
If you set this target with `utf8` you'll get unknown characters when pasting.
Another thing to note is the `wrap_html` function. While setting plain html works on Linux, Windows uses it's own (unnecessary) format. This function takes html fragment string and returns formatted bytes object.
`wrap_html` is only available on Windows.

To list available targets/formats:

```python
>>> klembord.get(['TARGETS'])
{'TARGETS': ['TARGETS', 'SAVE_TARGETS', 'UTF8_STRING', 'STRING']}
```

### Clipboard persistence on Linux

As of version 0.1.3 klembord supports storing content in clipboard after application
exit. You do need to call `klembord.store()` explicitly. Note that this method
raises `AttributeError` on Windows.

### Selection object

If you need to access `PRIMARY` selection at the same time as clipboard or you prefer working with objects rather than module level functions, you can use `Selection` objects.

```python
from klembord import Selection
```

These objects have the same methods as module level functions, with `klembord.init(SELECTION)` being the `Selection.__init__(SELECTION)`.

## Why klembord

klembord means clipboard in dutch. Since every reasonable name in english was taken on pypi, I decided to cosult a dictionary.
Now you might think since there're so many packages for clipboard access `klembord` is unnecessary.
Alas, all the other packages only work with plain text, depend on heavy toolkits or external executables, and in one particular case the entire package simply imports copy and paste functions from pyperclip.
I found the situation rather sad, so I decided to write `klembord`.

## Bugs and limitations

* Setting binary formats should work in theory but it's mostly untested.
* Setting/getting Windows built in binary formats (e.g. `CF_BITMAP`) doesn't work and WILL crash python. These require special handling which is currently not implemented in `klembord`
