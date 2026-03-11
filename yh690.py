#!/usr/bin/env python3
import os
import glob
from pathlib import Path
import struct
from datetime import datetime, timedelta
from decimal import Decimal
from dataclasses import dataclass
from matplotlib import pyplot as plt
import matplotlib.dates as mdates
import numpy as np
"""
Read DJMed CPAP files Yuwell YH-690
"""


DATA = Path("data") / "YH690"

                
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


@dataclass
class CPAPFile:
    start: datetime
    end: datetime
    mode: int
    ramp_time: int
    device_serial: str
    logs: list[CPAPLogLine]

    @classmethod
    def from_directory(cls, directory_name: Path) -> "CPAPFile":
        # files are the same as the directory name with the first digit missing? Maybe there are more than one?
        # There are three files per session?
        # *d.bys - RT Flow Rate, every 1/10th of a second
        # *m.bys - Minute summary data
        # *s.bys - Session summary data
        log_lines = []
        for summary in glob.glob(pathname="*s.bys", root_dir=directory_name):
            session_name = summary.replace("s.bys", "")
            with open(directory_name / f"{session_name}s.bys", "rb") as summary_handle:
                u1 = summary_handle.read(2)
                start_year, start_month, start_day, start_hour, start_minute, start_second = struct.unpack("BBBBBB", summary_handle.read(6))
                end_year, end_month, end_day, end_hour, end_minute, end_second = struct.unpack("BBBBBB", summary_handle.read(6))

                log_start = datetime(2000 + start_year, start_month, start_day, start_hour, start_minute, start_second)
                log_end = datetime(2000 + end_year, end_month, end_day, end_hour, end_minute, end_second)

                u2 = summary_handle.read(18)
                model_serial = summary_handle.read(16).decode()

                u3 = summary_handle.read(2)
                u_year, u_month, u_day, u_hour, u_minute, u_second = struct.unpack("BBBBBB", summary_handle.read(6))
                u_date = datetime(2000 + u_year, u_month, u_day, u_hour, u_minute, u_second)
                mode, = struct.unpack("B", summary_handle.read(1))
                u4 = summary_handle.read(18)
                fps_level, ramp = struct.unpack("BB", summary_handle.read(2))
                print(f"Log start: {log_start}")
                print(f"Log end: {log_end}")
                print(f"Model serial: {model_serial}")
                print(f"Unknown date: {u_date}")  # Matches start date?
                print(f"FPS Level: {fps_level}")
                print(f"Ramp: {ramp}")
            
            with open(directory_name / f"{session_name}m.bys", "rb") as minute_handle:
                start_year, start_month, start_day, start_hour, start_minute, start_second = struct.unpack("BBBBBB", minute_handle.read(6))
                record_count, = struct.unpack("h", minute_handle.read(2))

                minutes_start = datetime(2000 + start_year, start_month, start_day, start_hour, start_minute, start_second)

                print(f"Minutes start: {minutes_start}")
                print(f"Total minute records: {record_count}")

                for minute in range(record_count):
                    # OAI is incorrect, check all event flags
                    pressure, u7, oai, cai, hi = struct.unpack("BBBBB", minute_handle.read(5))
                    u5 = minute_handle.read(5)
                    leakage, = struct.unpack("B", minute_handle.read(1))
                    u6 = minute_handle.read(7)

                    log_time = minutes_start + timedelta(minutes=minute)

                    log_lines.append(CPAPLogLine(log_time, pressure / 10, leakage / 10, oai, hi, cai))
                    print(f"Pressure: {pressure}, OAI: {oai}, CAI: {cai}, HI: {hi}, Leakage: {leakage}")

            with open(directory_name / f"{session_name}d.bys", "rb") as flow_handle:
                start_year, start_month, start_day, start_hour, start_minute, start_second = struct.unpack("BBBBBB", flow_handle.read(6))
                record_count, = struct.unpack("h", flow_handle.read(2))

                flow_start = datetime(2000 + start_year, start_month, start_day, start_hour, start_minute, start_second)

                print(f"Flow start: {flow_start}")
                print(f"Flow record count: {record_count}")

                for _ in range(record_count):
                    dataset_1 = [struct.unpack("B", flow_handle.read(1)) for _ in range(600)]
                    dataset_2 = [struct.unpack("B", flow_handle.read(1)) for _ in range(600)]
                    print(dataset_1)
                    print(dataset_2)

        return cls(
            log_start,
            log_end,
            mode,
            ramp,
            model_serial,
            log_lines
        )


SHOW_CHARTS = True

def main():
    """
    For the time being, this just charts the minute logs in matplotlib
    """
    for file in os.scandir(DATA):
        # Sessions are in directories with the name structure of 8 numbers
        if not file.is_dir() or len(file.name) != 8:
            continue

        log_file = CPAPFile.from_directory(Path(file))
        if SHOW_CHARTS:
            print(log_file.logs)
            times = np.array([log.logged_time for log in log_file.logs])
            pressures = np.array([log.pressure for log in log_file.logs])
            leakages = np.array([log.leakage for log in log_file.logs])
            hi = np.array([log.hi for log in log_file.logs])
            oai = np.array([log.oai for log in log_file.logs])
            cai = np.array([log.cai for log in log_file.logs])

            fig, ax = plt.subplots(figsize=(30, 15))
            ax.plot(times, pressures)
            ax.plot(times, leakages)
            ax.plot(times, hi)
            ax.plot(times, oai)
            ax.plot(times, cai)

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
