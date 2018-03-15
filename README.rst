=============================================================
*dAwebAPI* - A Python library to access dA-compatible webAPIs
=============================================================

.. image:: https://img.shields.io/badge/License-GPLv3-red.svg
.. image:: https://img.shields.io/badge/python-2.7%7C3.5-green.svg


- Fork the code on `github <https://github.com/radjkarl/daWebApi>`_




Installation
^^^^^^^^^^^^

**dAwebAPI** is listed in the Python Package Index. You can install it typing::

    pip install dAwebAPI

Usage
^^^^^

Access dA-compatible webAPIs in the same way you'd access a local api:

.. code:: python

    import WebAPI S = WebAPI(<ADDRESS>) 
    print(dir(S)) # print all available functions
    print(S.aFunction.__doc__) #print a doctstring
    print(S.api_md()) #print api in makdown format
    print(S.aFunction(arg1, arg2, kwarg1=1, kwarg2='aa', kwargs=True)) 


Function output is formated depending on the functions signature.