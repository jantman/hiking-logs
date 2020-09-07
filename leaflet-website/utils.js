function pointsToTrackPoints(data) {
    return data.map(function (item) {
        var trkpt = L.latLng(item.lat, item.lng, item.alt);
        trkpt.meta = item.meta;
        return trkpt;
    });
}

function drawTrack(rawPoints, name) {
  visibleTrack = L.featureGroup();
  trackPoints = pointsToTrackPoints(rawPoints);

  // create a polyline from an arrays of LatLng points
  var polyline = L.multiOptionsPolyline(trackPoints, {
      multiOptions: {
          optionIdxFn: function (latLng) {
              var i, hr = latLng.meta.cpm,
                  zones = [0, 5, 10, 15, 20, 25, 30, 35, 40]; // beats per minute

              for (i = 0; i < zones.length; ++i) {
                  if (hr <= zones[i]) {
                      return i;
                  }
              }
              return zones.length;
          },
          options: [
              {color: '#0000FF'}, {color: '#0040FF'}, {color: '#0080FF'}, // below zone
              {color: '#00FFB0'}, {color: '#00E000'}, {color: '#80FF00'}, // in zone
              {color: '#FFFF00'}, {color: '#FFC000'}, {color: '#FF0000'}  // above zone
          ]
      },
      weight: 5,
      lineCap: 'butt',
      opacity: 0.75,
      smoothFactor: 1
  }).bindPopup(name).addTo(visibleTrack);
  return visibleTrack;
}
