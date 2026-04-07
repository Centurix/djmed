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
Read DJMed CPAP files Yuwell BreathCare II
"""


DATA = Path("data") / "YH830"

                
class InvalidCPAPFormat(Exception):
    ...


@dataclass
class CPAPLogLine:
    logged_time: datetime
    pressure: Decimal
    initial_pressure: Decimal
    ramp: Decimal
    tidal_volume: Decimal
    leakage: Decimal
    minute_volume: Decimal
    inspiratory_ratio: Decimal
    respiratory_rate: Decimal
    oai: int
    hi: int
    cai: int


@dataclass
class CPAPFile:
    start: datetime
    end: datetime
    ramp_time: int
    initial_pressure: Decimal
    minimum_pressure: Decimal
    humidity: int
    device_serial: str
    logs: list[CPAPLogLine]

    @classmethod
    def from_file(cls, file_name: Path) -> "CPAPFile":
        with open(file_name, "rb") as cpap_file:
            start_year, start_month, start_day, start_hour, start_minute, start_second = struct.unpack("hBBBBB", cpap_file.read(7))
            end_year, end_month, end_day, end_hour, end_minute, end_second = struct.unpack("hBBBBB", cpap_file.read(7))
            record_count, = struct.unpack("h", cpap_file.read(2))
            _ = cpap_file.read(5)
            humidity, = struct.unpack("B", cpap_file.read(1))
            _ = cpap_file.read(17)
            serial, = struct.unpack("16s", cpap_file.read(16))
            _ = cpap_file.read(5)

            log_start = datetime(start_year, start_month, start_day, start_hour, start_minute, start_second)
            log_end = datetime(end_year, end_month, end_day, end_hour, end_minute, end_second)

            log_lines = []

            for minute in range(record_count):
                _ = cpap_file.read(12)
                pressure, = struct.unpack("B", cpap_file.read(1))
                initial_pressure, = struct.unpack("B", cpap_file.read(1))
                _ = cpap_file.read(4)
                ramp, = struct.unpack("B", cpap_file.read(1))
                _ = cpap_file.read(2)
                tidal_volume, = struct.unpack("h", cpap_file.read(2))
                leak_volume, = struct.unpack("B", cpap_file.read(1))
                _ = cpap_file.read(1)
                minute_volume, = struct.unpack("B", cpap_file.read(1))
                _ = cpap_file.read(5)
                inspiratory_ratio, = struct.unpack("B", cpap_file.read(1))
                _ = cpap_file.read(2)
                respiratory_rate, = struct.unpack("B", cpap_file.read(1))
                oai, = struct.unpack("B", cpap_file.read(1))
                hi, = struct.unpack("B", cpap_file.read(1))
                _, = struct.unpack("B", cpap_file.read(1))
                cai, = struct.unpack("B", cpap_file.read(1))
                _ = cpap_file.read(1)

                log_time = log_start + timedelta(minutes=minute)

                # Missing AH, HI events (possibly 1/0)
                log_lines.append(CPAPLogLine(
                    log_time,
                    pressure / 10, 
                    initial_pressure / 10,
                    ramp,
                    tidal_volume,
                    leak_volume, 
                    minute_volume,
                    inspiratory_ratio,
                    respiratory_rate,
                    oai, 
                    hi, 
                    cai
                ))

        return cls(
            log_start,
            log_end,
            ramp,
            initial_pressure / 10,
            initial_pressure / 10,
            humidity,
            serial.decode(),
            log_lines
        )


SHOW_CHARTS = True

def main():
    """
    For the time being, this just charts the minute logs in matplotlib
    """
    for file in sorted(os.scandir(DATA), key=lambda e: e.name):
        log_file = CPAPFile.from_file(file)
        if SHOW_CHARTS:
            # print(log_file.logs)
            times = np.array([log.logged_time for log in log_file.logs])
            pressures = np.array([log.pressure for log in log_file.logs])
            initial_pressures = np.array([log.initial_pressure for log in log_file.logs])
            ramps = np.array([log.ramp for log in log_file.logs])
            tidal_volumes = np.array([log.tidal_volume for log in log_file.logs])
            leakages = np.array([log.leakage for log in log_file.logs])
            minute_volumes = np.array([log.minute_volume for log in log_file.logs])
            inspiratory_ratios = np.array([log.inspiratory_ratio for log in log_file.logs])
            respiratory_rate = np.array([log.respiratory_rate for log in log_file.logs])
            hi = np.array([log.hi for log in log_file.logs])
            oai = np.array([log.oai for log in log_file.logs])
            cai = np.array([log.cai for log in log_file.logs])

            fig, ax = plt.subplots(figsize=(30, 15))
            ax.plot(times, pressures)
            ax.plot(times, initial_pressures)
            ax.plot(times, ramps)
            ax.plot(times, tidal_volumes)
            ax.plot(times, leakages)
            ax.plot(times, minute_volumes)
            ax.plot(times, inspiratory_ratios)
            ax.plot(times, respiratory_rate)
            ax.plot(times, hi)
            ax.plot(times, oai)
            ax.plot(times, cai)

            locator = mdates.SecondLocator(interval=500)
            ax.xaxis.set_major_locator(locator)
            ax.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M:%S'))

            fig.autofmt_xdate()
            ax.set_xlabel("Time")
            ax.set_ylabel("CPAP Pressure (cmH2O)")
            ax.set_title(f"FILE: {file.name}: Starting {log_file.start.strftime('%Y-%m-%d')} (Between: {log_file.start.strftime('%H:%M')} and {log_file.end.strftime('%H:%M')}, Duration: {log_file.end - log_file.start})")
            plt.grid()
            plt.show()


if __name__ == "__main__":
    main()
