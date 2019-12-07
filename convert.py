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
        self, gpx, weight_lbs, pack_start_lbs, pack_end_lbs, terrain_factor,
        rmr
    ):
        """
        Initialize GpxCalories estimator.

        Terrain factor values suggested by the interactive version of this
        script were taken from
        https://www.researchgate.net/publication/284162748_TERRAIN_FACTORS_FOR_
        PREDICTING_WALKING_AND_LOAD_CARRIAGE_ENERGY_COSTS_REVIEW_AND_REFINEMENT

        Richmond, Paul & Potter, Adam & Santee, William. (2015).
        TERRAIN FACTORS FOR PREDICTING WALKING AND LOAD CARRIAGE ENERGY COSTS:
        REVIEW AND REFINEMENT. Journal of Sport and Human Performance.
        3. 10.12922/jshp.0067.2015.

        And are:

        * Paved road: 1.0
        * Gravel/dirt road: 1.2
        * Mud: 1.5
        * Wet clay/ice: 1.7
        * Sand: 2.0 (approximate)
        * Swamp: 3.5

        I generally use 1.2 for everything, and assume that time and slope will
        handle terrain variation.

        :param gpx: GPX object containing the data we need. Not required if
          ``gpx_path`` is provided.
        :param weight_lbs: Hiker's weight in pounds.
        :param pack_start_lbs: Pack starting weight in pounds.
        :param pack_end_lbs: Pack ending weight in pounds.
        :param terrain_factor: Terrain factor for Pandolf equation.
        :param rmr: Resting Metabolic Rate in ml O2/kg/min
        """
        self.gpx = gpx
        self.body_mass = weight_lbs * 0.45359237
        self.pack_start_mass = pack_start_lbs * 0.45359237
        self.pack_end_mass = pack_end_lbs * 0.45359237
        self.terrain_factor = terrain_factor
        self.rmr = rmr

    def run(self, downsample=1):
        """
        Generate the calorie count estimates for the GPX track.

        According to some random sources on the Internet, the average adult
        should burn approximately 440 cal/hour hiking. For a ballpark.
        """
        """
        cloned_gpx = self.gpx.clone()
        cloned_gpx.reduce_points(2000, min_distance=10)
        cloned_gpx.smooth(vertical=True, horizontal=True)
        cloned_gpx.smooth(vertical=True, horizontal=False)
        moving_time, stopped_time, moving_distance, stopped_distance, \
        max_speed_ms = cloned_gpx.get_moving_data()
        ud = self.gpx.get_uphill_downhill()
        elev = self.gpx.get_elevation_extremes()
        print({
            'track_start': self.gpx.get_time_bounds().start_time,
            'track_end': self.gpx.get_time_bounds().end_time,
            'duration_sec': self.gpx.get_duration(),
            'num_points': self.gpx.get_points_no(),
            'moving_time': moving_time,
            'stopped_time': stopped_time,
            'moving_distance': moving_distance,
            'stopped_distance': stopped_distance,
            'max_speed_ms': max_speed_ms,
            '2d_horizontal_distance': self.gpx.length_2d(),
            'total_elev_inc': ud.uphill,
            'total_elev_dec': ud.downhill,
            'min_elev': elev.minimum,
            'max_elev': elev.maximum
        })
        """
        mass_loss_per_point = (
            self.pack_start_mass - self.pack_end_mass
        ) / self.gpx.get_points_no()
        pack_mass = self.pack_start_mass
        last_point = None
        cal_pandolf = 0
        cal_ludlow = 0
        for point, _, _, idx in gpx.walk():
            if last_point is None:
                last_point = point
                continue
            pack_mass -= mass_loss_per_point
            if idx % downsample != 0:
                continue
            logger.debug(
                'Point at (%s,%s) -> %s',
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
            cal_pandolf += self.pandolf(
                pack_mass, speed, grade, time_diff
            )
            cal_ludlow += self.ludlow_weyand(
                grade, speed, time_diff
            )
            last_point = point
        print('Pandolf calories: %s' % cal_pandolf)
        print('Ludlow Weyand calories: %s' % cal_ludlow)

    def pandolf(self, pack_kg, speed_ms, grade_pct, duration_sec):
        logger.debug(
            'pack_kg=%s speed_ms=%s grade_pct=%s duration_sec=%s',
            pack_kg, speed_ms, grade_pct, duration_sec
        )
        hours = duration_sec / 60.0 / 60.0
        W = self.body_mass
        L = pack_kg
        n = self.terrain_factor
        G = grade_pct
        V = speed_ms
        watts = (
            1.5 * W + 2.0 * (W + L) * pow(L / W, 2) +
            n * (W + L) * (1.5 * pow(V, 2) + 0.35 * V * G)
        )
        cf = 0
        if G < 0:
            # add Santee correction factor for negative grade
            cf = (
                n * (
                    (G * (W + L) * V) / 3.5 -
                    ((W + L) * pow(G + 6.0, 2) / W) +
                    (25.0 * pow(V, 2))
                )
            )
        calories_per_hour = (watts + cf) / 4184.0 * 60.0 * 60.0
        logger.debug(
            'Grade is %s; watts=%s add Santee cf=%s; final=%s; calories per '
            'hour=%s hours=%s',
            grade_pct, watts, cf, watts + cf, calories_per_hour, hours
        )
        return calories_per_hour * hours

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
    p.add_argument('-t', '--terrain-factor', dest='terrain', action='store',
                   type=float, default=None,
                   help='Terrain factor (for Pandolf equation)')
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
    if args.terrain is None:
        """
        These values were taken from
        https://www.researchgate.net/publication/284162748_TERRAIN_FACTORS_FOR_
        PREDICTING_WALKING_AND_LOAD_CARRIAGE_ENERGY_COSTS_REVIEW_AND_REFINEMENT

        Richmond, Paul & Potter, Adam & Santee, William. (2015).
        TERRAIN FACTORS FOR PREDICTING WALKING AND LOAD CARRIAGE ENERGY COSTS:
        REVIEW AND REFINEMENT. Journal of Sport and Human Performance.
        3. 10.12922/jshp.0067.2015.
        """
        sys.stderr.write('Paved road: 1.0\n')
        sys.stderr.write('Gravel/dirt road: 1.2\n')
        sys.stderr.write('Mud: 1.5\n')
        sys.stderr.write('Wet clay/ice: 1.7\n')
        sys.stderr.write('Sand: 2.0\n')  # approximate
        sys.stderr.write('Swamp: 3.5\n')
        sys.stderr.write(
            'I generally use 1.2 for everything, and assume that time and '
            'slope will handle terrain variation.\n'
        )
        args.terrain = float(input('Terrain factor: ').strip())
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
    args = parse_args(sys.argv[1:])
    # set logging level
    if args.verbose > 1:
        set_log_debug()
    elif args.verbose == 1:
        set_log_info()
    files = list(glob.glob('./*.json'))
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
        gpx, args.weight, args.pack_start, args.pack_end, args.terrain, args.rmr
    )
    cls.run()
    cls.run(downsample=2)
    cls.run(downsample=3)
    cls.run(downsample=4)
    cls.run(downsample=5)
    cls.run(downsample=8)
    cls.run(downsample=10)
