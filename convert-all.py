#!/home/jantman/GIT/pizero-gpslog/venv/bin/python

import sys
import argparse
import logging
import json
import csv
from glob import iglob
import os

from gpxpy.gpx import GPX, GPXTrack, GPXTrackSegment, GPXTrackPoint
from gpxpy.gpxfield import TIME_TYPE
from gpxpy import parse

FORMAT = "[%(asctime)s %(levelname)s] %(message)s"
logging.basicConfig(level=logging.WARNING, format=FORMAT)
logger = logging.getLogger()


class GpsConverter:

    def __init__(self, fpath):
        self.fpath = fpath
        self.csv_path = self.fpath + '.csv'
        self.gpx_path = self.fpath + '.gpx'
        self.geojson_path = self.fpath + '.geojson'

    def convert(self):
        lines = self._read_json(self.fpath)
        logger.info('Read %d lines', len(lines))
        if not os.path.exists(self.csv_path):
            self.to_csv(lines)
        if not os.path.exists(self.gpx_path):
            logger.info('Writing to: %s', self.gpx_path)
            gpx = self._gpx_for_logs(lines)
            with open(self.gpx_path, 'w') as fh:
                fh.write(gpx.to_xml())
            logger.info('Wrote: %s', self.gpx_path)
        if not os.path.exists(self.geojson_path):
            logger.info('Writing to: %s', self.geojson_path)
            j = self.to_geojson(lines)
            with open(self.geojson_path, 'w') as fh:
                fh.write(json.dumps(j, sort_keys=True, indent=4))
            logger.info('Wrote: %s', self.geojson_path)

    def to_geojson(self, lines):
        raise NotImplementedError("not implemented")
        result = {}
        for item in lines:
            try:
                tpv = item['tpv'][0]
                sky = item['sky'][0]
                alt = tpv.get(
                    'alt', item['gst'][0].get('alt', prev_alt)
                )
                prev_alt = alt
                p = GPXTrackPoint(
                    latitude=tpv['lat'],
                    longitude=tpv['lon'],
                    elevation=alt,
                    time=TIME_TYPE.from_string(tpv['time']),
                    speed=tpv['speed'],
                    horizontal_dilution=sky.get('hdop', None),
                    vertical_dilution=sky.get('vdop', None),
                    position_dilution=sky.get('pdop', None)
                )
                if tpv['mode'] == 2:
                    p.type_of_gpx_fix = '2d'
                elif tpv['mode'] == 3:
                    p.type_of_gpx_fix = '3d'
                if 'satellites' in sky:
                    p.satellites = len(sky['satellites'])
                cpm = item.get('_extra_data', {}).get('data', {}).get('cpm', 0)
                seg.points.append(p)
            except Exception:
                sys.stderr.write(
                    'Exception loading line %d:\n' % item['lineno']
                )
                raise
        return result

    def to_csv(self, lines):
        headers = ['Latitude', 'Longitude', 'Time', 'CPM']
        logger.info('Writing to: %s', self.csv_path)
        with open(self.csv_path, 'w', newline='') as csvfile:
            writer = csv.writer(csvfile, delimiter=',', quotechar='"')
            writer.writerow(headers)
            for l in lines:
                lat = l.get('tpv', [{}])[0].get('lat')
                lon = l.get('tpv', [{}])[0].get('lon')
                if lat is None or lon is None:
                    logger.debug('Skip line: %s', l)
                    continue
                writer.writerow([
                    lat, lon,
                    l.get('_extra_data', {}).get('data', {}).get('cpm', 0)
                ])
        logger.info('Wrote: %s', self.csv_path)

    def _gpx_for_logs(self, logs):
        g = GPX()
        track = GPXTrack()
        track.source = 'pizero-gpslog gmc-500'
        g.tracks.append(track)
        seg = GPXTrackSegment()
        track.segments.append(seg)
        prev_alt = 0.0

        for item in logs:
            try:
                tpv = item['tpv'][0]
                sky = item['sky'][0]
                alt = tpv.get(
                    'alt', item['gst'][0].get('alt', prev_alt)
                )
                prev_alt = alt
                p = GPXTrackPoint(
                    latitude=tpv['lat'],
                    longitude=tpv['lon'],
                    elevation=alt,
                    time=TIME_TYPE.from_string(tpv['time']),
                    speed=tpv['speed'],
                    horizontal_dilution=sky.get('hdop', None),
                    vertical_dilution=sky.get('vdop', None),
                    position_dilution=sky.get('pdop', None)
                )
                if tpv['mode'] == 2:
                    p.type_of_gpx_fix = '2d'
                elif tpv['mode'] == 3:
                    p.type_of_gpx_fix = '3d'
                if 'satellites' in sky:
                    p.satellites = len(sky['satellites'])
                cpm = item.get('_extra_data', {}).get('data', {}).get('cpm', 0)
                seg.points.append(p)
            except Exception:
                sys.stderr.write(
                    'Exception loading line %d:\n' % item['lineno']
                )
                raise
        return g

    def _read_json(self, fpath):
        logger.info('Reading from: %s', fpath)
        result = []
        with open(fpath, 'r') as fh:
            for lineno, line in enumerate(fh.readlines()):
                line = line.strip()
                if line == '':
                    continue
                try:
                    j = json.loads(line)
                    result.append(j)
                except Exception as ex:
                    logger.error(
                        'Error loading line %d: %s', lineno, ex
                    )
        return result


def parse_args(argv):
    """
    parse arguments/options

    this uses the new argparse module instead of optparse
    see: <https://docs.python.org/2/library/argparse.html>
    """
    p = argparse.ArgumentParser(description='GPS Log Converter')
    p.add_argument('-v', '--verbose', dest='verbose', action='count', default=0,
                   help='verbose output. specify twice for debug-level output.')
    args = p.parse_args(argv)
    return args


def set_log_info():
    """set logger level to INFO"""
    set_log_level_format(logging.INFO,
                         '%(asctime)s %(levelname)s:%(name)s:%(message)s')


def set_log_debug():
    """set logger level to DEBUG, and debug-level output format"""
    set_log_level_format(
        logging.DEBUG,
        "%(asctime)s [%(levelname)s %(filename)s:%(lineno)s - "
        "%(name)s.%(funcName)s() ] %(message)s"
    )


def set_log_level_format(level, format):
    """
    Set logger level and format.

    :param level: logging level; see the :py:mod:`logging` constants.
    :type level: int
    :param format: logging formatter format string
    :type format: str
    """
    formatter = logging.Formatter(fmt=format)
    logger.handlers[0].setFormatter(formatter)
    logger.setLevel(level)


if __name__ == "__main__":
    args = parse_args(sys.argv[1:])
    # set logging level
    if args.verbose > 1:
        set_log_debug()
    elif args.verbose == 1:
        set_log_info()
    for f in iglob('**/*.json', recursive=True):
        GpsConverter(f).convert()
