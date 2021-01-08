# pyAsyncFluke5440B
Python3 AsyncIO Fluke 5440B driver. This library requires Python [asyncio](https://docs.python.org/3/library/asyncio.html) and AsyncIO library for the GPIB adapter.

## Supported GPIB Hardware
|Device|Supported|Tested|Comments|
|--|--|--|--|
|[AsyncIO Prologix GPIB library](hhttps://github.com/PatrickBaus/pyAsyncPrologixGpib)|:heavy_check_mark:|:x:|  |
|[AsyncIO linux-gpib wrapper](https://github.com/PatrickBaus/pyAsyncGpib)|:heavy_check_mark:|:heavy_check_mark:|To be released

Tested using Linux, should work for Mac OSX, Windows and any OS with Python support.

## Setup

There are currently no packages available. To install the library, clone the repository into your project folder and install the required packages. This setup assumes, that linux-gpib was downloded to
[~/linux-gpib-code/].


```bash
virtualenv env  # virtual environment, optional
source env/bin/activate
pip install -r requirements.txt
# pip install -e ~/linux-gpib-code/linux-gpib-user/language/python/
```

## Usage
All examples assume, that the GPIB library is copied to the same root folder as the library. Either run
```bash
git clone https://github.com/PatrickBaus/pyAsyncPrologixGpib    # or alternativeliy
# git clone https://github.com/PatrickBaus/pyAsyncGpib

```
or download the source code from the git repository and copy it yourself.

A simple example for setting the output voltage.
```python
from pyAsyncFluke5440B.Fluke_5440B import Fluke_5440B

from pyAsyncGpib.pyAsyncGpib.AsyncGpib import AsyncGpib

# The default GPIB address is 7.
fluke5440b = Fluke_5440B(connection=AsyncGpib(name=0, pad=7))


# This example will print voltage data to the console
async def main():
    try: 
        # No need to explicitely bring up the GPIB connection. This will be done by the instrument.
        await fluke5440b.connect()
        await fluke5440b.set_output(10.0)
        await fluke5440b.set_output_enabled(True)

    except asyncio.TimeoutError:
        logging.getLogger(__name__).error('Timeout. Error: %s', await fluke5440b.get_error())
    finally:
        # Disconnect from the instrument. We may safely call diconnect() on a non-connected device, even
        # in case of a connection error
        await fluke5440b.disconnect()

try:
    asyncio.run(main(), debug=True)
except KeyboardInterrupt:
    # The loop will be canceled on a KeyboardInterrupt by the run() method, we just want to suppress the exception
    pass
```

See [examples/](examples/) for more working examples.

### Methods
```python
   async def get_id()
```
This function returns returns the instrument name and the software version string.

```python
   async def connect()
```
Connect to the GPIB device. This function must be called from the loop and does all the setup of the GPIB adapter and the instrument.

```python
   async def disconnect()
```
Disconnect from the instrument and clean up. This call will also automatically remove the local lockout if set.

```python
   async def read()
```
Read the instrument buffer.

___Returns___
* [string or list of strings] : Returns a UTF-8 encoded string or a list of strings if multiple commands where given.

```python
   async def write(self, cmd, test_error=False):
```
Write a string or bytestring to the instrument.

___Arguments___
* `value` [string or Bytes] : If a string is given, it will be ASCII encoded.
* `test_error` [bool] : If set, check if the command was accepted, otherwise raise an error. This will cause an extra roundtrip delay. The default is false, but its use is recommended.

___Raises___
* Raises a `DeviceError` if `test_error` is set and the command was not accepted by the instrument.

```python
   async def query(self, cmd, test_error=False):
```
Write a string or bytestring to the instrument and return the result.

___Arguments___
* `value` [string or Bytes] : If a string is given, it will be ASCII encoded.
* `test_error` [bool] : If set, check if the command was accepted, otherwise raise an error. This will cause an extra roundtrip delay. The default is false, but its use is recommended.

___Returns___
* [string or list of strings] : Returns a UTF-8 encoded string or a list of strings if multiple commands where given.

___Raises___
* Raises a `DeviceError` if `test_error` is set and the command was not accepted by the instrument.

```python
   async def reset()
```
Place the instrument in standby, enable voltage mode, set the output voltage to 0.0, disable the divider output, the external guard mode and external sense mode.

```python
   async def local()
```
Enable the front panel buttons, if they the instrument is in local lock out.

```python
   async def get_terminator()
```
Returns the line terminator sent by the instrument.

___Returns___
* [[TerminatorType](#terminatortype)] : The type of terminator used.

```python
   async def get_separator()
```
Returns the separator used by the instrument to separate multiple queries .

___Returns___
* [[SeparatorType](#separatortype)] : The type of terminator used.

```python
   async def set_mode(value)
```
Enabled either voltage or current boost mode using an external Fluke 5205A power amplifier or a Fluke 5220A transconductance amplifier.

___Arguments___
* `value` [[ModeType](#modetype)] : The boost mode selected.

___Raises___
* Raises a `DeviceError` if there is problem connecting to the amplifier.

```python
   async def set_output_enabled(enabled)
```
Sets the output to either standby or operating.

___Arguments___
* `enabled` [bool] : Set to enable the output.

___Raises___
* Raises a `DeviceError` if an error is detected.

```python
   async def get_output()
```
Returns the output currently set.

___Returns___
* [Decimal] : The output as a Decimal to preserve the precision.

```python
   async def set_output(value, test_error=True)
```

___Arguments___
* `value` [float or Decimal] : The desired output.
* `test_error` [bool] : If set, check if the command was accepted, otherwise raise an error.

___Raises___
* Raises a `ValueError` if the value is out of range. If the value is above or below ±1500 V, an error will be raised regardless of the `test_error` flag.
* Raises a `DeviceError` if an error is detected.

```python
   async def set_internal_sense(enabled)
```
If the load resistance is greater than 1 MΩ, 2-wire calibration can be unsed. Otherwise cable resistance can reduce accuracy. Use internal sense for 2-wire calibrations.

___Arguments___
* `enabled` [bool] : If set, the voltage sense input internally connected to the output binding posts.

```python
   async def set_internal_guard(enabled)
```
If set, the guard is internally connected to the output LO terminal. Use this if the device being calibrated has floating inputs. If calibrating devices with grounded inputs, connect the guard terminal to the input LO of the device and disable the internal guard.

___Arguments___
* `enabled` [bool] : Set to enable the internal guard or unset to float the internal guard.

### Enums

#### ModeType
```python
class ModeType(Enum):
    NORMAL = "BSTO"
    VOLTAGE_BOOST = "BSTV"
    CURRENT_BOOST = "BSTC"
```

#### TerminatorType
```python
class TerminatorType(Enum):
    EOI       = 0
    CR_LF_EOI = 1
    LF_EOI    = 2
    CR_LF     = 3
    LF        = 4
```

#### SeparatorType
```python
class SeparatorType(Enum):
    COMMA = 0
    COLON = 1
```

## Versioning

I use [SemVer](http://semver.org/) for versioning. For the versions available, see the [tags on this repository](https://github.com/PatrickBaus/pyAsyncPrologix/tags).

## Authors

* **Patrick Baus** - *Initial work* - [PatrickBaus](https://github.com/PatrickBaus)

## License


This project is licensed under the GPL v3 license - see the [LICENSE](LICENSE) file for details

