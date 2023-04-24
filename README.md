[![pylint](https://github.com/PatrickBaus/pyAsyncFluke5440B/actions/workflows/pylint.yml/badge.svg)](https://github.com/PatrickBaus/pyAsyncHP3478A/actions/workflows/pylint.yml)
[![PyPI](https://img.shields.io/pypi/v/fluke5440b_async)](https://pypi.org/project/fluke5440b_async/)
![PyPI - Python Version](https://img.shields.io/pypi/pyversions/fluke5440b_async)
![PyPI - Status](https://img.shields.io/pypi/status/fluke5440b_async)
[![code style](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)
# fluke5440b-async
Python3 AsyncIO Fluke 5440B driver. This library requires Python [asyncio](https://docs.python.org/3/library/asyncio.html) and AsyncIO library for the GPIB adapter.

The library is fully type-hinted.

> :warning: The following features are not supported (yet):
> - External calibration: I do not have the means to test this. If you want to help, open a ticket and we can get this done
> - Setting and retrieving DUUT tolerances and errors. I believe this is best done in software on the host computer and not done internally in the calibrator. If you really need that featuer open a ticket.

## Supported GPIB Hardware
|Device|Supported|Tested|Comments|
|--|--|--|--|
|[AsyncIO Prologix GPIB library](https://github.com/PatrickBaus/pyAsyncPrologixGpib)|:heavy_check_mark:|:heavy_check_mark:|  |
|[AsyncIO linux-gpib wrapper](https://github.com/PatrickBaus/pyAsyncGpib)|:heavy_check_mark:|:heavy_check_mark:|  |

Tested using Linux, but should work on Mac OSX, Windows or any OS with Python support.

## Documentation
The full documentation can be found on GitHub Pages:
[https://patrickbaus.github.io/pyAsyncFluke5440B/](https://patrickbaus.github.io/pyAsyncFluke5440B/). I use the
[Numpydoc](https://numpydoc.readthedocs.io/en/latest/format.html) style for documentation and
[Sphinx](https://www.sphinx-doc.org/en/master/index.html) for compiling it.

# Setup
To install the library in a virtual environment (always use venvs with every project):
```bash
python3 -m venv env  # virtual environment, optional
source env/bin/activate  # only if the virtual environment is used
pip install fluke5440b-async
```

All examples assume that a GPIB library is installed as well. Either run
```bash
pip install prologix-gpib-async    # or alternatively
# pip install async-gpib
```

# Usage
> :warning: The calibrator does not like excessive serial polling. So, when using the Prologix adapter, one might see warnings like this:
> *Got error during waiting: ErrorCode.GPIB_HANDSHAKE_ERROR. If you are using a Prologix adapter, this can be safely ignored at this point.*
> These are harmless and can be ignored.

The library uses an asynchronous context manager to make cleanup easier. You can use either the
context manager syntax or invoke the calls manually:

```python
async with Fluke_5440B(connection=gpib_device) as fluke5440b:
    # Add your code here
    ...
```

```python
try:
    fluke5440b = Fluke_5440B(connection=gpib_device)
    await fluke5440b.connect()
    # your code
finally:
    await fluke5440b.disconnect()
```


A simple example for setting the output voltage.
```python
from pyAsyncFluke5440B.Fluke_5440B import Fluke_5440B

from pyAsyncGpib.pyAsyncGpib.AsyncGpib import AsyncGpib


# This example will print voltage data to the console
async def main():
    # The default GPIB address is 7.
    async with Fluke_5440B(connection=AsyncGpib(name=0, pad=7)) as fluke5440b:
        # No need to explicitely bring up the GPIB connection. This will be done by the instrument.
        await fluke5440b.set_output(10.0)
        await fluke5440b.set_output_enabled(True)


try:
    asyncio.run(main(), debug=True)
except KeyboardInterrupt:
    # The loop will be canceled on a KeyboardInterrupt by the run() method, we just want to suppress the exception
    pass
```

See [examples/](examples/) for more working examples.

## Versioning

I use [SemVer](http://semver.org/) for versioning. For the versions available, see the [tags on this repository](https://github.com/PatrickBaus/pyAsyncPrologix/tags).

## Authors

* **Patrick Baus** - *Initial work* - [PatrickBaus](https://github.com/PatrickBaus)

## License


This project is licensed under the GPL v3 license - see the [LICENSE](LICENSE) file for details
