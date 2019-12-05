# hiking-logs

[![Project Status: Active – The project has reached a stable, usable state and is being actively developed.](https://www.repostatus.org/badges/latest/active.svg)](https://www.repostatus.org/#active)

GPS tracks and other info from my hikes

## Setup

``virtualenv . && source bin/activate && pip install pizero-gpslog``

## Usage

1. ``source bin/activate && cd pizero-gpslog_output``
2. Create a directory for the new hike, ``cd`` to it, and copy the pizero-gpslog ``.json`` output file there.
3. ``../../convert.py``

## Calorie Calculations and Inaccuracies

For estimated calorie consumption over hikes, this script outputs values from two different equations: the commonly-used Pandolf [^1] equation with the decline extension developed by Santee [^2] (and using terrain factors from [^3]), and the modern equation developed by Ludlow and Weyand [^4].

While these formulas are scientifically rigorous, the way they're applied in this script is definitely not and should be considered a relatively rough estimate. Among the more troublesome points with my method of applying these formulas to data collected in uncontrolled field conditions with the type of GPS logging commonly used by hikers are:

1. At best, I weigh myself and my pack before a hike and the pack after. At worst, I may only weigh before or after and estimate the pack's starting or ending weight. The calculations performed by this program assume a constant linear decrease in pack weight over the course of the hike, with weight being decremented from starting to ending at each point in the GPS track. Assuming a short day hike where only water is taken out of the pack, this shouldn't be too inaccurate, though it certainly does skew the results especially for hikes that mix flat and steep terrain along with increased water intake on difficult terrain.
2. The grade/slope is taken from GPS elevation information with no supplemental topographical references. In addition to the inherent inaccuracies in GPS data, this also means that GPS sampling rate can have a large impact on the results; a GPS sampling rate of exactly the same time it takes you to cross a mountain could result in a calculated 0% grade.
3. The Pandolf (and Santee variant) equation relies on a terrain factor to account for increased work crossing various types of terrain (essentially from a paved road at one end of the spectrum to a swamp at the other). This program currently only accepts a single terrain factor for the whole hike/track.

## Footnotes

[^1]: https://www.ncbi.nlm.nih.gov/pubmed/908672 Pandolf KB, Givoni B, Goldman RF: Predicting energy expenditure with loads while standing or walking very slowly. J Appl Physiol Respir Environ Exerc Physiol 1977; 43(4): 577–81.

[^2]: Santee WR, Blanchard LA, Speckman KL, Gonzalez JA, Wallace RF: Load Carriage Model Development and Testing with Field Data. Technical Note. Natick, MA, U.S. Army Research Institute of Environmental Medicine, Report No.: ADA#415788, 2003.

[^3]: https://www.researchgate.net/publication/284162748_TERRAIN_FACTORS_FOR_PREDICTING_WALKING_AND_LOAD_CARRIAGE_ENERGY_COSTS_REVIEW_AND_REFINEMENT Richmond, Paul & Potter, Adam & Santee, William. (2015). TERRAIN FACTORS FOR PREDICTING WALKING AND LOAD CARRIAGE ENERGY COSTS: REVIEW AND REFINEMENT. Journal of Sport and Human Performance. 3. 10.12922/jshp.0067.2015.

[^4]: https://www.physiology.org/doi/full/10.1152/japplphysiol.00504.2017 Walking economy is predictably determined by speed, grade, and gravitational load. Lindsay W. Ludlow and Peter G. Weyand. Journal of Applied Physiology 2017 123:5, 1288-1302
