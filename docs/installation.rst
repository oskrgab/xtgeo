.. highlight:: shell

Installation
============

XTGeo is a cross-platform library written in Python 3.

From pip
--------

For a selection of platforms (Linux/Windows/MacOS; all 64bit).

.. code-block:: console

   $ pip install xtgeo


From GitHub
------------

A C and C++ compiler are required to ``pip install`` directly from
the GitHub repository.

.. code-block:: console

   $ pip install git+https://github.com/equinor/xtgeo


From downloaded sources
-----------------------

A C and C++ compiler are required to build XTGeo from source.

* gcc/g++ on Linux (Version 4 and later), or clang/clang++
* clang/clang++ on macOS
* Visual studio 2015 and 2017 on Windows

The sources for XTGeo can be downloaded from the repository on 
`GitHub <https://github.com/equinor/xtgeo>`_.

You can either clone the public repository:

.. code-block:: console

   $ git clone git@github.com:equinor/xtgeo

Also you will need test data at the same folder level as the source:


Modifying and testing XTGeo
---------------------------

If you wish to make changes to the code or run the tests you can find 
instructions and tips for how to do so in the 
:doc:`Contributing document <contributing>`.


In the browser (WASM / Pyodide)
-------------------------------

This fork ships an Emscripten/WebAssembly wheel that loads in Pyodide, so you
can use XTGeo in the browser with no native install. See
:doc:`XTGeo in the browser <wasm>` for the ``micropip`` install line, the pinned
Pyodide version you must match, a usage example, and the documented limitations.


Within Equinor
--------------

Within Equinor the stable release is pre-installed so all you have
to do is:

.. code-block:: python

   import xtgeo


