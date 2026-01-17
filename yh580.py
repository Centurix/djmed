#!/usr/bin/env python3
import os
from pathlib import Path
import struct
from datetime import datetime, timedelta
from decimal import Decimal
from dataclasses import dataclass, field
from matplotlib import pyplot as plt
import matplotlib.dates as mdates
import numpy as np
"""
Read DJMed CPAP files for the Yuwell YH-580
"""


DATA = Path("data") / "YH580" / "YHSD-NEW.BYS"

                
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
    spo2: Decimal
    pulse: Decimal


@dataclass
class CPAPSession:
    start: datetime
    end: datetime
    mode: int
    ramp_time: int
    initial_pressure: Decimal
    pressure_setting: int
    minimum_pressure: Decimal
    maximum_pressure: Decimal
    humidity: int
    fps_level: int
    oai_count: int
    hi_count: int
    average_leak_volume: Decimal
    average_pressure: Decimal
    offset: int
    u7: int  #  CAI count?
    length: int
    log_lines: list[CPAPLogLine] = field(default_factory=lambda: [])


@dataclass
class CPAPFile:
    start: datetime
    end: datetime
    mode: int
    ramp_time: int
    initial_pressure: Decimal
    pressure_setting: int
    minimum_pressure: Decimal
    maximum_pressure: Decimal
    humidity: int
    fps_level: int
    device_serial: str
    sessions: list[CPAPSession]

    @classmethod
    def from_file(cls, file_name: Path) -> "CPAPFile":
        with open(file_name, "rb") as cpap_file:
            magic_number = struct.unpack("BBBB", cpap_file.read(4))
            mode, ramp, initial_pressure, pressure_setting, maximum_pressure, minimum_pressure, humidity, fps_level = struct.unpack("BBBBBBBB", cpap_file.read(8))
            unknown1 = cpap_file.read(19)
            record_count, = struct.unpack("h", cpap_file.read(2))
            unknown2 = cpap_file.read(99)
            serial, = struct.unpack("16s", cpap_file.read(16))
            unknown3 = cpap_file.read(144) # 0xFF
            unknown4 = cpap_file.read(12) # Some data
            unknown5 = cpap_file.read(2768) # 0xFF

            sessions: list[CPAPSession] = []

            for session in range(record_count):
                start_year, start_month, start_day, start_hour, start_minute, start_second = struct.unpack("BBBBBB", cpap_file.read(6))
                end_year, end_month, end_day, end_hour, end_minute, end_second = struct.unpack("BBBBBB", cpap_file.read(6))

                log_start = datetime(2000 + start_year, start_month, start_day, start_hour, start_minute, start_second)
                log_end = datetime(2000 + end_year, end_month, end_day, end_hour, end_minute, end_second)

                mode, ramp, initial_pressure, pressure_setting, maximum_pressure, minimum_pressure, humidity, fps_level = struct.unpack("BBBBBBBB", cpap_file.read(8))
                oai_count, hi_count = struct.unpack("BB", cpap_file.read(2))
                u3, u4 = struct.unpack("BB", cpap_file.read(2)) # Suspect CAI
                avg_pressure, avg_leak_vol = struct.unpack("BB", cpap_file.read(2))
                offset, = struct.unpack(">H", cpap_file.read(2))
                u7, = struct.unpack("B", cpap_file.read(1))
                if u7 > 0:
                    print(f"Found a value in u7: {u7}, {offset}")
                session_minutes, = struct.unpack("B", cpap_file.read(1))

                sessions.append(CPAPSession(
                    log_start,
                    log_end,
                    mode,
                    ramp,
                    initial_pressure,
                    pressure_setting,
                    minimum_pressure,
                    maximum_pressure,
                    humidity,
                    fps_level,
                    oai_count,
                    hi_count,
                    avg_leak_vol,
                    avg_pressure,
                    offset + 30208,
                    u7,
                    session_minutes,
                    []
                ))

            # unknown6 = cpap_file.read(22906), This read is unnecessary, but this seeks to the beginning of the session log lines
            session_blocks = []

            for session in sessions:
                cpap_file.seek(session.offset)
                try:
                    for minute in range(session.length):
                        leakage, pressure, spo2, oai, hi, pulse, cai = struct.unpack("BBBBBBB", cpap_file.read(7))
                        if minute == 0 and leakage != 249:
                            break
                        elif minute == 0:
                            session_blocks.append({
                                "date": session.start,
                                "start": session.offset,
                                "end": session.offset + (session.length * 7),
                                "u7": session.u7
                            })

                        session.log_lines.append(CPAPLogLine(
                            log_start + timedelta(minutes=minute),
                            pressure,
                            leakage,
                            oai,
                            hi,
                            cai,
                            0,
                            spo2,
                            pulse
                        ))
                except struct.error as se:
                    pass

            print("Blocks:")
            print(session_blocks)

        return cls(
            log_start,
            log_end,
            mode,
            ramp,
            initial_pressure / 10,
            pressure_setting,
            minimum_pressure / 10,
            maximum_pressure / 10,
            humidity,
            fps_level,
            serial,
            sessions
        )


SHOW_CHARTS = True

def main():
    """
    For the time being, this just charts the minute logs in matplotlib
    """
    log_file = CPAPFile.from_file(DATA)
    if SHOW_CHARTS:
        for session in log_file.sessions:
            times = np.array([log.logged_time for log in session.log_lines])
            if len(times) > 0:
                pressures = np.array([log.pressure for log in session.log_lines])
                leakages = np.array([log.leakage for log in session.log_lines])
                hi = np.array([log.hi for log in session.log_lines])
                oai = np.array([log.oai for log in session.log_lines])
                cai = np.array([log.cai for log in session.log_lines])

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
                ax.set_title(f"FILE: {session.start}: Starting {session.start.strftime('%Y-%m-%d')} (Between: {session.start.strftime('%H:%M')} and {session.end.strftime('%H:%M')}, Duration: {session.end - session.start})")
                plt.grid()
                plt.show()


if __name__ == "__main__":
    main()
