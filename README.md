# pyAsyncFluke5440B
Python3 AsyncIO Fluke 5440B driver. This library requires Python [asyncio](https://docs.python.org/3/library/asyncio.html) and AsyncIO library for the GPIB adapter.

> :warning: The following features are not supported (yet):
> - External calibration: I do not have the means to test this. If you want to help, open a ticket and we can get this done
> - Setting and retrieving DUUT tolerances and errors. I believe this is best done in software on the host computer and not done internally in the calibrator. If you really need that featuer open a ticket.
> - Selftest. Fortunately, I only own a calibrator that passes the selft test, so I cannot test the self test function on a machine that throws errors. I have implemented the self test routines and from what I inferred from the manual, it _should_ work with faulty machines and throw an exception, but who knows. If you can test this. I would be gratefuly about feedback.

## Supported GPIB Hardware
|Device|Supported|Tested|Comments|
|--|--|--|--|
|[AsyncIO Prologix GPIB library](https://github.com/PatrickBaus/pyAsyncPrologixGpib)|:heavy_check_mark:|:x:|  |
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
* [Decimal] : The output as a `Decimal` to preserve the precision.

```python
   async def set_output(value, test_error=True)
```
Set the output of the calibrator. If an output greater than ±22 V is set, the calibrator will automatically go to STBY for safety reasons. Call `set_output_enabled(True)` to reenable the output.

___Arguments___
* `value` [float or Decimal] : The desired output.
* `test_error` [bool] : If set, check if the command was accepted, otherwise raise an error.

___Raises___
* Raises a `ValueError` if the value is out of range. If the value is above or below ±1500 V, an error will be raised regardless of the `test_error` flag.
* Raises a `DeviceError` if an error is detected.

```python
   async def set_internal_sense(enabled)
```
If the load resistance is greater than 1 MΩ, 2-wire calibration can be used. Otherwise cable resistance will reduce accuracy. Use internal sense for 2-wire calibrations. See page 2-13 of the operator manual for details.

___Arguments___
* `enabled` [bool] : If set, the voltage sense input internally connected to the output binding posts.

```python
   async def set_internal_guard(enabled)
```
If set, the guard is internally connected to the output LO terminal. Use this if the device being calibrated has floating inputs. If calibrating devices with grounded inputs, connect the guard terminal to the input LO of the device and disable the internal guard. See page 2-14 of the operator manual for details.

___Arguments___
* `enabled` [bool] : Set to enable the internal guard or unset to float the internal guard.

```python
   async def set_divider(enabled)
```
Enable the internal dividet to reduce the output noise and increase the resolution. Do not enable the external sense connection via `set_internal_sense(False)` as this will decrease the accuracy. The divider has an output impedance of 450 Ω. The load should ideally be greater than 1 GΩ to keep the loading error below 1 ppm. See page 3-10 of the operator manual for details. 

___Arguments___
* `enabled` [bool] : Set to enable the divided output.

```python
   async def get_voltage_limit()
```
Get the voltage limit set on the instrument. It will raise an error, when in current boost mode.

___Returns___
* [tuple of Decimals] : Returns the voltage limit as a tuple of (positive, negative)

___Raises___
* Raises a `DeviceError` when in current boost mode.

```python
   async def set_voltage_limit(value, value2=None)
```
Set the upper or lower voltage limit.

___Arguments___
* `value` [float or Decimal] : If one value is passed, the voltage limit will be set depending on the polarity of the value.
* `value2` [float or Decimal] : If two values are passed, one needs to be negative and and both limits will be set.

___Raises___
* Raises a `ValueError` if the limits are out of bounds

```python
   async def get_current_limit()
```
Get the current limit set on the instrument. This will raise an error, when in voltage boost mode.

___Returns___
* [tuple of Decimals] : Returns the current limit as a tuple of (positive, negative)

___Raises___
* Raises a `DeviceError` when in voltage boost mode.

```python
   async def set_current_limit(value, value2=None)
```
Set the upper or lower current limit.

___Arguments___
* `value` [float or Decimal] : If one value is passed, the current limit will be set depending on the polarity of the value.
* `value2` [float or Decimal] : If two values are passed, one needs to be negative and and both limits will be set.

___Raises___
* Raises a `ValueError` if the limits are out of bounds

```python
   async def selftest_digital()
```
Test the main CPU, the front panel CPU and the guard CPU. It will take about 5 seconds during which the instrument hardware is blocked. See page 3-19 of the operator manual for details. 

___Raises___
* Raises a `SelftestError` on error.

```python
   async def selftest_analog()
```
Test the ADC, the low voltage part and the oven. It will take about 4 minutes during which the instrument hardware is blocked. See page 3-19 of the operator manual for details. 

___Raises___
* Raises a `SelftestError` on error.

```python
   async def selftest_hv()
```
Test the ADC and the high voltage part. It will take about 1 minute during which the instrument hardware is blocked. See page 3-20 of the operator manual for details. 

___Raises___
* Raises a `SelftestError` on error.

```python
   async def selftest_all()
```
Run all three self-tests.

___Raises___
* Raises a `SelftestError` on error.

```python
   async def acal()
```
Run the internal calibration routine. It will take about 6.5 minutes during which the instrument hardware is blocked. See page 3-2 of the operator manual for details. 

```python
   async def get_calibration_constants()
```
Query the calibration constants and gain shifts with respect to the previous internal calibration. See page 3-18 of the operator manual for details. 

___Returns___
* [Dict] : A dictionary containing `Decimal` values with the following keys: `gain_0.2V`, `gain_2V`, `gain_10V`, `gain_20V`, `gain_250V`, `gain_1000V`, `offset_10V_pos`, `offset_20V_pos`, `offset_250V_pos`, `offset_1000V_pos`, `offset_10V_neg`, `offset_20V_neg`, `offset_250V_neg`, `offset_1000V_neg`, `gain_shift_10V`, `gain_shift_20V`, `gain_shift_250V`, `gain_shift_1000V`, `resolution_ratio`, `adc_gain`

```python
   async def get_rs232_baud_rate()
```
Return in the baud rate in bit/s.

```python
   async def set_rs232_baud_rate(value)
```
Set the baud rate of the RS-232 interface.

___Arguments___
* `value` [int or float] : One out of the  following values: `50`, `75`, `110`, `134.5`, `150`, `200`, `300`, `600`, `1200`, `1800`, `2400`, `4800`, `9600`.

___Raises___
* Raises a `ValueError` the value is invalid.

```python
   async def set_enable_rs232(enabled)
```
Enable the RS-232 printer port.

___Arguments___
* `enabled` [bool] : Set to enable the printer port.

```python
   async def get_status()
```
Get the status of the instrument. The status contains the mode the instrument is running in, like boost mode, or state of the external sense connection, etc.

___Returns___
* [[StatusFlags](#statusflags)] : The flags set resemble the status of the instrument.

```python
   async def get_error()
```
Get the last error thrown by the instrument if any. It is recommended to check for errors after using the `write()` function, if the `test_error` parameter is not set.

___Returns___
* [[ErrorCode](#errorcode)] : Returns `ErrorCode.NONE` if there was no error or the error code if there was an error.

```python
   async def get_state()
```
If the instrument is running longterm jobs, it signals its current state. Use this to poll the state.

___Returns___
* [[State](#state)] : Returns `State.IDLE` if the instrument can accept new requests to change the hardware configuration.

```python
   async def serial_poll()
```
Poll the serial output buffer of the device. This can be used to query for the SRQ bit, when device requests service, has encountered an error or is busy.

___Returns___
* [[SerialPollFlags](#serialpollflags)] : Returns a concise version of the current device state.

```python
   async def get_srq_mask()
```
Get the SRQ mask. This mask is used to determine, when the device will pull down the SRQ line.

___Returns___
* [[SrqMask](#srqmask)] : Each field set, will trigger an SRQ request when encountered.

```python
   async def set_srq_mask(value)
```

___Arguments___
* `value` [[SrqMask](#srqmask)] : The mask to select on which condition an SRQ request is triggered by the device.

### Enums

#### ErrorCode
```python
class ErrorCode(Enum):
    NONE                              = 0
    BOOST_INTERFACE_CONNECTION_ERROR  = 144
    BOOST_INTERFACE_MISSING           = 145
    BOOST_INTERFACE_VOLTAGE_TRIP      = 146
    BOOST_INTERFACE_CURRENT_TRIP      = 147
    GPIB_HANDSHAKE_ERROR              = 152
    TERMINATOR_ERROR                  = 153
    SEPARATOR_ERROR                   = 154
    UNKNOWN_COMMAND                   = 155
    INVALID_PARAMTER                  = 156
    BUFFER_OVERFLOW                   = 157
    INVALID_CHARACTER                 = 158
    RS232_ERROR                       = 160
    PARAMTER_OUT_OF_RANGE             = 168
    OUTPUT_OUTSIDE_LIMITS             = 169
    LIMIT_OUT_OF_RANGE                = 170
    DIVIDER_OUT_OF_RANGE              = 171
    INVALID_SENSE_MODE                = 172
    INVALID_GUARD_MODE                = 173
    INVALID_COMMAND                   = 175
```

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

#### State
```python
class State(Enum):
    IDLE                     = 0
    CALIBRATING_ADC          = 16
    ZEROING_10V_pos          = 32
    ZEROING_10V_neg          = 33
    ZEROING_20V_pos          = 34
    ZEROING_20V_neg          = 35
    ZEROING_250V_pos         = 36
    ZEROING_250V_neg         = 37
    ZEROING_1000V_pos        = 38
    ZEROING_1000V_neg        = 39
    CALIBRATING_GAIN_10V_pos = 48
    CALIBRATING_GAIN_20V_pos = 49
    CALIBRATING_GAIN_HV_pos  = 50
    CALIBRATING_GAIN_HV_neg  = 51
    CALIBRATING_GAIN_20V_neg = 52
    CALIBRATING_GAIN_10V_neg = 53
    EXT_CAL_10V              = 64
    EXT_CAL_20V              = 65
    EXT_CAL_250V             = 66
    EXT_CAL_1000V            = 67
    EXT_CAL_2V               = 68
    EXT_CAL_02V              = 69
    EXT_CAL_10V_NULL         = 80
    EXT_CAL_20V_NULL         = 81
    EXT_CAL_250V_NULL        = 82
    EXT_CAL_1000V_NULL       = 83
    EXT_CAL_2V_NULL          = 84
    EXT_CAL_02V_NULL         = 85
    CAL_N1_N2_RATIO          = 96
    SELF_TEST_MAIN_CPU       = 112
    SELF_TEST_FRONTPANEL_CPU = 113
    SELF_TEST_GUARD_CPU      = 114
    SELF_TEST_LOW_VOLTAGE    = 128
    SELF_TEST_HIGH_VOLTAGE   = 129
    SELF_TEST_OVEN           = 130
    PRINTING                 = 208
    WRITING_TO_NVRAM         = 224
    RESETTING                = 240
```

### Flags

#### SerialPollFlags
```python
class SerialPollFlags(Flag):
    NONE               = 0b0
    DOING_STATE_CHANGE = 1 << 2
    MSG_RDY            = 1 << 3
    OUTPUT_SETTLED     = 1 << 4
    ERROR_CONDITION    = 1 << 5
    SRQ                = 1 << 6
```

#### SrqMask
```python
class SrqMask(Flag):
    NONE                = 0b0
    DOING_STATE_CHANGE  = 1 << 2
    MSG_RDY             = 1 << 3
    OUTPUT_SETTLED      = 1 << 4
    ERROR_CONDITION     = 1 << 5
```

#### StatusFlags
```python
class StatusFlags(Flag):
    VOLTAGE_MODE           = 1 << 0
    CURRENT_BOOST_MODE     = 1 << 1
    VOLTAGE_BOOST_MODE     = 1 << 2
    DIVIDER_ENABLED        = 1 << 3
    INTERNAL_SENSE_ENABLED = 1 << 4
    OUTPUT_ENABLED         = 1 << 5
    INTERNAL_GUARD_ENABLED = 1 << 6
    REAR_OUTPUT_ENABLED    = 1 << 7
```

## Versioning

I use [SemVer](http://semver.org/) for versioning. For the versions available, see the [tags on this repository](https://github.com/PatrickBaus/pyAsyncPrologix/tags).

## Authors

* **Patrick Baus** - *Initial work* - [PatrickBaus](https://github.com/PatrickBaus)

## License


This project is licensed under the GPL v3 license - see the [LICENSE](LICENSE) file for details

