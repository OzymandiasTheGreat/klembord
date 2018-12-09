#!/usr/bin/env python3

import os.path
from setuptools import setup

with open(os.path.join(os.path.dirname(__file__), 'README.md')) as fd:
	long_description = fd.read()

classifiers = [
	'Development Status :: 5 - Production/Stable',
	'Environment :: X11 Applications',
	'Environment :: Win32 (MS Windows)',
	'Intended Audience :: Developers',
	'License :: OSI Approved :: MIT License',
	'Operating System :: Microsoft :: Windows',
	'Operating System :: POSIX',
	'Operating System :: POSIX :: Linux',
	'Programming Language :: Python :: 3']

setup(
	name='klembord',
	version='0.1.3',
	description='Full toolkit agnostic cross-platform clipboard access',
	long_description=long_description,
	long_description_content_type='text/markdown',
	url='https://github.com/OzymandiasTheGreat/klembord',
	author='Tomas Ravinskas',
	author_email='tomas.rav@gmail.com',
	license='MIT',
	classifiers=classifiers,
	packages=['klembord'],
	package_dir={'klembord': 'package'},
	python_requires='>=3.4',
	install_requires=['python-xlib'])
