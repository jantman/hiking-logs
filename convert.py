#!/usr/bin/env python

import sys
import argparse
import logging
import glob
import json
import os
from math import pow

from pizero_gpslog.converter import GpxConverter
import pint
from gpxpy.gpx import GPX, GPXTrack, GPXTrackSegment, GPXTrackPoint
from gpxpy.gpxfield import TIME_TYPE
from gpxpy import parse

FORMAT = "[%(asctime)s %(levelname)s] %(message)s"
logging.basicConfig(level=logging.WARNING, format=FORMAT)
logger = logging.getLogger()


class GpxCalories(object):

    def __init__(
        self, gpx, weight_lbs, pack_start_lbs, pack_end_lbs, rmr
    ):
        """
        Initialize GpxCalories estimator.

        :param gpx: GPX object containing the data we need. Not required if
          ``gpx_path`` is provided.
        :param weight_lbs: Hiker's weight in pounds.
        :param pack_start_lbs: Pack starting weight in pounds.
        :param pack_end_lbs: Pack ending weight in pounds.
        :param rmr: Resting Metabolic Rate in ml O2/kg/min
        """
        self.gpx = gpx
        self.body_mass = weight_lbs * 0.45359237
        self.pack_start_mass = pack_start_lbs * 0.45359237
        self.pack_end_mass = pack_end_lbs * 0.45359237
        self.rmr = rmr

    def run(self, downsample=1):
        """
        Generate the calorie count estimates for the GPX track.

        According to some random sources on the Internet, the average adult
        should burn approximately 440 cal/hour hiking. For a ballpark.
        """
        mass_loss_per_point = (
            self.pack_start_mass - self.pack_end_mass
        ) / self.gpx.get_points_no()
        pack_mass = self.pack_start_mass
        last_point = None
        cal_ludlow = 0
        for point, _, _, idx in gpx.walk():
            if last_point is None:
                last_point = point
                continue
            pack_mass -= mass_loss_per_point
            if idx % downsample != 0:
                continue
            logger.debug(
                'Last Point at (%s,%s) -> %s',
                last_point.latitude, last_point.longitude, last_point.elevation
            )
            logger.debug(
                'Point at (%s,%s) -> %s',
                point.latitude, point.longitude, point.elevation
            )
            elev_gain = point.elevation - last_point.elevation  # meters
            distance = point.distance_2d(last_point)  # meters
            time_diff = point.time_difference(last_point)  # seconds
            grade = 0.0  # percent
            if distance != 0:
                grade = (elev_gain / distance) * 100.0  # percent
            speed = point.speed_between(last_point)  # meters/second
            logger.debug(
                'distance=%s meters; time_diff=%s seconds; '
                'elev_gain=%s meters; grade=%s%%',
                distance, time_diff, elev_gain, grade
            )
            cal_ludlow += self.ludlow_weyand(
                grade, speed, time_diff
            )
            last_point = point
        return cal_ludlow

    def ludlow_weyand(self, G, V, duration_sec):
        v_O2_rest = self.rmr
        hours = duration_sec / 60.0 / 60.0
        # G is positive surface inclination in percent grade
        # V is velocity in meters/second
        C1 = 0.32
        v_O2_walk_min = 3.28
        C2 = 0.19
        C3 = 2.66
        Cdecline = 0.73
        cf = 0
        if G < 0:
            # not entirely sure about this part
            G = 0
            cf = Cdecline
        ml_o2_per_kg_per_min = (
            v_O2_rest +
            (C1 * G) + v_O2_walk_min +
            (1 + (C2 * G)) * (C3 * pow(V, 2))
        ) + cf
        ml_o2_per_min = ml_o2_per_kg_per_min * self.body_mass
        l_o2_per_min = ml_o2_per_min / 1000.0
        kcal_per_min = l_o2_per_min * 5
        kcal_per_hour = kcal_per_min * 60.0
        return kcal_per_hour * hours


def parse_args(argv):
    """
    parse arguments/options

    this uses the new argparse module instead of optparse
    see: <https://docs.python.org/2/library/argparse.html>
    """
    p = argparse.ArgumentParser(description='GPS Log Converter')
    p.add_argument('-v', '--verbose', dest='verbose', action='count', default=0,
                   help='verbose output. specify twice for debug-level output.')
    p.add_argument('-w', '--body-weight', dest='weight', action='store',
                   type=float, default=None, help='Body weight in pounds')
    p.add_argument('-p', '--pack-start', dest='pack_start', action='store',
                   type=float, default=None, help='Pack start weight in pounds')
    p.add_argument('-P', '--pack-end', dest='pack_end', action='store',
                   type=float, default=None, help='Pack end weight in pounds')
    p.add_argument('-H', '--height', dest='height', action='store',
                   type=float, default=None, help='Height in cm')
    p.add_argument('-a', '--age', dest='age', action='store',
                   type=float, default=None, help='Age in years')
    p.add_argument('-R', '--rmr', dest='rmr', action='store', type=float,
                   default=None,
                   help='Resting metabolic rate in ml O2/kg/minute. This can be'
                        'specified instead of the height, age, and gender '
                        'parameters. All of the sources that I could find '
                        'to calculate approximate RMR use gender-specific '
                        'formulas. This allows overriding those. For '
                        'calculation (if not specifying this parameter) we use '
                        'the Mifflin-St Jeor formula.')
    p.add_argument('-m', '--male', dest='male', action='store_true',
                   default=False,
                   help='Calculation is for a male. Defaults to false (female);'
                        'see help for -R/--rmr for more information')
    args = p.parse_args(argv)
    if args.weight is None:
        args.weight = float(input('Body weight in pounds: ').strip())
    if args.pack_start is None:
        args.pack_start = float(input('Pack start weight in pounds: ').strip())
    if args.pack_end is None:
        args.pack_end = float(input('Pack end weight in pounds: ').strip())
    if args.rmr is None:
        # using the Mifflin-St Jeor formula
        rmr = (10 * args.weight) + (6.25 * args.height) - (5 * args.age)
        if args.male:
            rmr += 5
        else:
            rmr -= 161
        # we now have RMR in calories per day; we need it in ml O2/kg/min
        l_per_day = rmr / 5.0
        l_per_minute = l_per_day / (60 * 24)
        args.rmr = l_per_minute / args.weight * 1000
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
    with open('cmdline.json', 'w') as fh:
        fh.write(json.dumps(sys.argv[1:]))
    args = parse_args(sys.argv[1:])
    # set logging level
    if args.verbose > 1:
        set_log_debug()
    elif args.verbose == 1:
        set_log_info()
    files = list(glob.glob('./20*.json'))
    assert len(files) == 1
    gpx_path = files[0].replace('.json', '.gpx')
    if os.path.exists(gpx_path):
        logger.info(
            'GPX file is present; already converted. Reading %s', gpx_path
        )
        with open(gpx_path, 'r') as fh:
            gpx = parse(fh)
    else:
        conv = GpxConverter(files[0], imperial=True)
        gpx = conv.convert()
        with open(gpx_path, 'w') as fh:
            fh.write(gpx.to_xml())
        logger.info('GPX file written to: %s', gpx_path)
        stats_text = conv.stats_text(conv.stats_for_gpx(gpx))
        with open(files[0] + '.stats', 'w') as fh:
            fh.write(stats_text)
        print(stats_text)
    cls = GpxCalories(
        gpx, args.weight, args.pack_start, args.pack_end, args.rmr
    )
    calories = {0: round(cls.run())}
    s = f'Estimated calories burned at original intervals: {calories[0]}\n'
    for n in [2, 3, 4, 5, 8, 10, 12, 20]:
        calories[n] = round(cls.run(downsample=n))
        s += 'Estimated calories burned downsampled to every ' \
             f'{n} points: {calories[n]}\n'
    with open('calories.json', 'w') as fh:
        fh.write(json.dumps(calories))
    with open('calories.txt', 'w') as fh:
        fh.write(s)
    print(s)
