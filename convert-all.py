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
        print('Loading: %s' % fpath)
        self.fpath = fpath
        self.csv_path = self.fpath + '.csv'
        self.gpx_path = self.fpath + '.gpx'
        self.leaflet_json_path = self.fpath + '.leaflet.json'
        logger.info('Reading: %s', fpath)
        self.lines = self._read_json(self.fpath)
        logger.info('Read %d lines', len(self.lines))

    def convert(self):
        if not os.path.exists(self.csv_path):
            self.to_csv(lines)
        if not os.path.exists(self.gpx_path):
            logger.info('Writing to: %s', self.gpx_path)
            gpx = self._gpx_for_logs(lines)
            with open(self.gpx_path, 'w') as fh:
                fh.write(gpx.to_xml())
            logger.info('Wrote: %s', self.gpx_path)
        jl, max_cpm = self.to_leaflet_json()
        if not os.path.exists(self.leaflet_json_path):
            logger.info('Writing to: %s', self.leaflet_json_path)
            with open(self.leaflet_json_path, 'w') as fh:
                fh.write(json.dumps(jl, sort_keys=True, indent=4))
            logger.info('Wrote: %s', self.leaflet_json_path)
        return jl, max_cpm

    def to_leaflet_json(self):
        result = []
        prev_alt = 0.0
        max_cpm = 0
        for idx, item in enumerate(self.lines):
            try:
                tpv = item['tpv'][0]
                sky = item['sky'][0]
                alt = tpv.get(
                    'alt', item['gst'][0].get('alt', prev_alt)
                )
                prev_alt = alt
                cpm = item.get('_extra_data', {}).get('data', {}).get('cpm', 0)
                p = {
                    'lat': tpv['lat'],
                    'lng': tpv['lon'],
                    'alt': alt,
                    'meta': {
                        'time': TIME_TYPE.from_string(tpv['time']).timestamp(),
                        'speed': tpv['speed'],
                        'hdop': sky.get('hdop', None),
                        'vdop': sky.get('vdop', None),
                        'pdop': sky.get('pdop', None),
                        'altitude': alt,
                        'cpm': cpm
                    }
                }
                if tpv['mode'] == 2:
                    p['meta']['fix'] = '2d'
                elif tpv['mode'] == 3:
                    p['meta']['fix'] = '3d'
                if 'satellites' in sky:
                    p['meta']['satellites'] = len(sky['satellites'])
                if cpm >= max_cpm:
                    max_cpm = cpm
                result.append(p)
            except Exception:
                logger.error(
                    'Error loading line %d: %s', idx, item
                )
                raise
        return result, max_cpm

    def to_csv(self):
        headers = ['Latitude', 'Longitude', 'Time', 'CPM']
        logger.info('Writing to: %s', self.csv_path)
        with open(self.csv_path, 'w', newline='') as csvfile:
            writer = csv.writer(csvfile, delimiter=',', quotechar='"')
            writer.writerow(headers)
            for l in self.lines:
                tpv = l['tpv'][0]
                lat = tpv['lat']
                lon = tpv['lon']
                if lat is None or lon is None:
                    logger.debug('Skip line: %s', l)
                    continue
                writer.writerow([
                    lat, lon,
                    l.get('_extra_data', {}).get('data', {}).get('cpm', 0)
                ])
        logger.info('Wrote: %s', self.csv_path)

    def _gpx_for_logs(self):
        g = GPX()
        track = GPXTrack()
        track.source = 'pizero-gpslog gmc-500'
        g.tracks.append(track)
        seg = GPXTrackSegment()
        track.segments.append(seg)
        prev_alt = 0.0

        for idx, item in enumerate(self.lines):
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
                logger.error(
                    'Error loading line %d: %s', idx, item
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
                    if j != []:
                        result.append(j)
                except Exception as ex:
                    logger.error(
                        'Error loading line %d: %s', lineno, ex
                    )
        return result


class Converter:

    def run(self):
        max_cpm = 0
        result = {
            'hiking': None, 'driving': None
        }
        for k in sorted(result.keys()):
            tracks, cpm = self._do_directory(k)
            if cpm >= max_cpm:
                max_cpm = cpm
            result[k] = tracks
        logger.info('Max CPM: %d', max_cpm)

    def _do_directory(self, path):
        logger.info('Doing directory: %s', path)
        max_cpm = 0
        tracks = []
        for f in iglob(f'pizero-gpslog_output/{path}/**/*.json', recursive=True):
            parts = f.split('/')[-1].split('.')
            if (
                len(parts) == 2 and
                parts[1] == 'json' and
                (parts[0].startswith('20') or parts[0].startswith('combined'))
            ):
                j, cpm = GpsConverter(f).convert()
                if cpm >= max_cpm:
                    max_cpm = cpm
                tracks.append(j)
        logger.info(
            'Directory %s: got %d tracks and max cpm %d',
            path, len(tracks), max_cpm
        )
        return tracks, max_cpm


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
    if args.verbose >= 1:
        set_log_debug()
    else:
        set_log_info()
    Converter().run()
    raise NotImplementedError("Get EXIF from photos, make GeoJSON or KML/GPX")
