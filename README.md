# hiking-logs

[![Project Status: Active – The project has reached a stable, usable state and is being actively developed.](https://www.repostatus.org/badges/latest/active.svg)](https://www.repostatus.org/#active)

GPS tracks and other info from my hikes

## Setup

``virtualenv . && source bin/activate && pip install pizero-gpslog``

## Usage

1. ``source bin/activate && cd pizero-gpslog_output``
2. Create a directory for the new hike or track, ``cd`` to it, and copy the pizero-gpslog ``.json`` output file there. If there's more than one, combine them with ``cat``.
3. For hikes: ``../../convert_hike.py``
4. ``cd`` back to the top directory and run ``./convert-all.py``

## Calorie Calculations and Inaccuracies

For estimated calorie consumption over hikes, this script outputs values from the modern equation developed by Ludlow and Weyand [^1].

While these formulas are scientifically rigorous, the way they're applied in this script is definitely not and should be considered a relatively rough estimate. Among the more troublesome points with my method of applying these formulas to data collected in uncontrolled field conditions with the type of GPS logging commonly used by hikers are:

1. At best, I weigh myself and my pack before a hike and the pack after. At worst, I may only weigh before or after and estimate the pack's starting or ending weight. The calculations performed by this program assume a constant linear decrease in pack weight over the course of the hike, with weight being decremented from starting to ending at each point in the GPS track. Assuming a short day hike where only water is taken out of the pack, this shouldn't be too inaccurate, though it certainly does skew the results especially for hikes that mix flat and steep terrain along with increased water intake on difficult terrain.
2. The grade/slope is taken from GPS elevation information with no supplemental topographical references. In addition to the inherent inaccuracies in GPS data, this also means that GPS sampling rate can have a large impact on the results; a GPS sampling rate of exactly the same time it takes you to cross a mountain could result in a calculated 0% grade.

## Footnotes

[^1]: https://www.physiology.org/doi/full/10.1152/japplphysiol.00504.2017 Walking economy is predictably determined by speed, grade, and gravitational load. Lindsay W. Ludlow and Peter G. Weyand. Journal of Applied Physiology 2017 123:5, 1288-1302
