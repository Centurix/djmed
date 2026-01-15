#!/usr/bin/env python3
import os
from pathlib import Path
import struct
from datetime import datetime, timedelta
from decimal import Decimal
from dataclasses import dataclass
from matplotlib import pyplot as plt
import matplotlib.dates as mdates
import numpy as np
"""
Read DJMed CPAP files Yuwell YH-550
"""


DATA = Path("data") / "YH550"

                
class InvalidCPAPFormat(Exception):
    ...


@dataclass
class CPAPLogLine:
    logged_time: datetime
    pressure: Decimal
    leakage: Decimal
    oai: int
    hi: int
    cai: int
    u6: int


@dataclass
class CPAPFile:
    start: datetime
    end: datetime
    mode: int
    ramp_time: int
    initial_pressure: Decimal
    minimum_pressure: Decimal
    maximum_pressure: Decimal
    humidity: int
    average_leak_volume: Decimal
    average_pressure: Decimal
    device_serial: str
    logs: list[CPAPLogLine]

    @classmethod
    def from_file(cls, file_name: Path) -> "CPAPFile":
        with open(file_name, "rb") as cpap_file:
            start_year, start_month, start_day, start_hour, start_minute, start_second = struct.unpack("BBBBBB", cpap_file.read(6))
            end_year, end_month, end_day, end_hour, end_minute, end_second = struct.unpack("BBBBBB", cpap_file.read(6))
            mode, ramp_up_time, initial_pressure, minimum_pressure, maximum_pressure = struct.unpack("BBBBB", cpap_file.read(5))
            unknown2 = cpap_file.read(1)
            humidity, = struct.unpack("B", cpap_file.read(1))
            unknown3 = cpap_file.read(7)
            average_leak_volume, = struct.unpack("B", cpap_file.read(1))
            unknown4 = cpap_file.read(1)
            average_pressure, = struct.unpack("B", cpap_file.read(1))
            unknown5 = cpap_file.read(1)
            serial, record_count = struct.unpack("16sh", cpap_file.read(18))
            unknown6 = cpap_file.read(2)
            unknown7, = struct.unpack("B", cpap_file.read(1))  # Always 0xF9?

            if unknown7 != 0xF9:
                raise InvalidCPAPFormat("Invalid CPAP format")

            log_start = datetime(2000 + start_year, start_month, start_day, start_hour, start_minute, start_second)
            log_end = datetime(2000 + end_year, end_month, end_day, end_hour, end_minute, end_second)

            log_lines = []

            for minute in range(record_count):
                pressure, = struct.unpack("B", cpap_file.read(1))
                u1, = struct.unpack("B", cpap_file.read(1))
                u2, = struct.unpack("B", cpap_file.read(1))
                oai, = struct.unpack("B", cpap_file.read(1))
                hi, = struct.unpack("B", cpap_file.read(1))
                cai, = struct.unpack("B", cpap_file.read(1))
                u6, = struct.unpack("B", cpap_file.read(1))
                u7, = struct.unpack("B", cpap_file.read(1))
                u8, = struct.unpack("B", cpap_file.read(1))
                leakage, = struct.unpack("B", cpap_file.read(1))

                log_time = log_start + timedelta(minutes=minute)

                # Always zero, one is possibly SPo2, another is the pulse rate
                # If we find values, we're interested to know
                if u6 > 0:
                    print(f"u6 threshold {u6}, {u1}, {u2}, {u7}, {u8} - {pressure}, {oai}, {hi}, {cai}, {leakage} from {file_name}, {log_time}")
                if u1 + u2 + u7 + u8 > 0:
                    raise InvalidCPAPFormat("Invalid CPAP format, unexpected data")

                # Missing AH, HI events (possibly 1/0)
                log_lines.append(CPAPLogLine(log_time, pressure / 10, leakage / 10, oai, hi, cai, u6))

        return cls(
            log_start,
            log_end,
            mode,
            ramp_up_time,
            initial_pressure / 10,
            minimum_pressure / 10,
            maximum_pressure / 10,
            humidity,
            average_leak_volume / 10,
            average_pressure / 10,
            serial,
            log_lines
        )


SHOW_CHARTS = False

def main():
    """
    For the time being, this just charts the minute logs in matplotlib
    """
    for file in os.scandir(DATA):
        log_file = CPAPFile.from_file(file)
        if SHOW_CHARTS:
            print(log_file.logs)
            times = np.array([log.logged_time for log in log_file.logs])
            pressures = np.array([log.pressure for log in log_file.logs])
            leakages = np.array([log.leakage for log in log_file.logs])
            hi = np.array([log.hi for log in log_file.logs])
            oai = np.array([log.oai for log in log_file.logs])
            cai = np.array([log.cai for log in log_file.logs])
            u6 = np.array([log.u6 for log in log_file.logs])

            fig, ax = plt.subplots(figsize=(30, 15))
            ax.plot(times, pressures)
            ax.plot(times, leakages)
            ax.plot(times, hi)
            ax.plot(times, oai)
            ax.plot(times, cai)
            ax.plot(times, u6)

            locator = mdates.SecondLocator(interval=500)
            ax.xaxis.set_major_locator(locator)
            ax.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M:%S'))

            fig.autofmt_xdate()
            ax.set_xlabel("Time")
            if log_file.mode == 0:
                ax.set_ylabel("CPAP Pressure (cmH2O)")
            else:
                ax.set_ylabel("APAP Pressure (cmH2O)")
            ax.set_title(f"FILE: {file.name}: Starting {log_file.start.strftime('%Y-%m-%d')} (Between: {log_file.start.strftime('%H:%M')} and {log_file.end.strftime('%H:%M')}, Duration: {log_file.end - log_file.start})")
            plt.grid()
            plt.show()


if __name__ == "__main__":
    main()
