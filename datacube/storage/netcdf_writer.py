# coding=utf-8
"""
Create netCDF4 Storage Units and write data to them
"""
from __future__ import absolute_import

import logging
import numbers
from datetime import datetime

import netCDF4
import numpy

from datacube.storage.masking import describe_flags_def
from datacube.model import GeoPolygon, CRS
from datacube.utils import data_resolution_and_offset

# pylint: disable=ungrouped-imports,wrong-import-order
try:
    from datacube.storage.netcdf_safestrings import SafeStringsDataset as Dataset
except TypeError:  # The above fails when netCDF4.Dataset is mocked, eg in RTD
    from netCDF4 import Dataset

from datacube import __version__

_LOG = logging.getLogger(__name__)

_STANDARD_COORDINATES = {
    'longitude': {
        'standard_name': 'longitude',
        'long_name': 'longitude',
        'axis': 'X'
    },
    'latitude': {
        'standard_name': 'latitude',
        'long_name': 'latitude',
        'axis': 'Y'
    },
    'x': {
        'standard_name': 'projection_x_coordinate',
        'long_name': 'x coordinate of projection',
        # 'axis': 'X'  # this makes gdal (2.0.0) think x is longitude and it does bad things to it (subtract 360)
    },
    'y': {
        'standard_name': 'projection_y_coordinate',
        'long_name': 'y coordinate of projection',
        # 'axis': 'Y'  # see x's axis comment above
    },
    'time': {
        'standard_name': 'time',
        'long_name': 'Time, unix time-stamp',
        'axis': 'T',
        'calendar': 'standard'
    }
}


def create_netcdf(netcdf_path, **kwargs):
    nco = Dataset(netcdf_path, 'w', **kwargs)
    nco.date_created = datetime.today().isoformat()
    nco.setncattr('Conventions', 'CF-1.6, ACDD-1.3')
    nco.history = ("NetCDF-CF file created by "
                   "datacube version '{}' at {:%Y%m%d}."
                   .format(__version__, datetime.utcnow()))
    return nco


def append_netcdf(netcdf_path):
    return Dataset(netcdf_path, 'a')


def create_coordinate(nco, name, labels, units):
    """
    :type nco: netCDF4.Dataset
    :type name: str
    :type labels: numpy.array
    :type units: str
    :return: netCDF4.Variable
    """
    labels = netcdfy_coord(labels)

    nco.createDimension(name, labels.size)
    var = nco.createVariable(name, labels.dtype, name)
    var[:] = labels

    var.units = units
    for key, value in _STANDARD_COORDINATES.get(name, {}).items():
        setattr(var, key, value)

    return var


def create_variable(nco, name, var, set_crs=False, attrs=None, **kwargs):
    """
    :param nco:
    :param name:
    :type var: datacube.model.Variable
    :param kwargs:
    :return:
    """
    if 'chunksizes' in kwargs:
        maxsizes = [len(nco.dimensions[dim]) for dim in var.dims]
        kwargs['chunksizes'] = [min(chunksize, maxsize) if chunksize and maxsize else chunksize
                                for maxsize, chunksize in zip(maxsizes, kwargs['chunksizes'])]

    assert var.dtype.kind != 'U'  # Creates Non CF-Compliant NetCDF File
    if var.dtype.kind == 'S' and var.dtype.itemsize > 1:
        nco.createDimension(name + '_nchar', size=var.dtype.itemsize)
        data_var = nco.createVariable(varname=name,
                                      datatype='S1',
                                      dimensions=tuple(var.dims) + (name + '_nchar',),
                                      fill_value=getattr(var, 'nodata', None),
                                      **kwargs)
    else:
        data_var = nco.createVariable(varname=name,
                                      datatype=var.dtype,
                                      dimensions=var.dims,
                                      fill_value=getattr(var, 'nodata', None),
                                      **kwargs)
    if set_crs:
        data_var.grid_mapping = 'crs'
    if getattr(var, 'units', None):
        data_var.units = var.units
    data_var.set_auto_maskandscale(False)
    return data_var


def _create_latlon_grid_mapping_variable(nco, crs):
    crs_var = nco.createVariable('crs', 'i4')
    crs_var.long_name = crs['GEOGCS']  # "Lon/Lat Coords in WGS84"
    crs_var.grid_mapping_name = 'latitude_longitude'
    crs_var.longitude_of_prime_meridian = 0.0
    return crs_var


def _write_albers_params(crs_var, crs):
    # http://spatialreference.org/ref/epsg/gda94-australian-albers/html/
    # http://cfconventions.org/Data/cf-conventions/cf-conventions-1.7/build/cf-conventions.html#appendix-grid-mappings
    crs_var.grid_mapping_name = 'albers_conical_equal_area'
    crs_var.standard_parallel = (crs.proj.standard_parallel_1,
                                 crs.proj.standard_parallel_2)
    crs_var.longitude_of_central_meridian = crs.proj.longitude_of_center
    crs_var.latitude_of_projection_origin = crs.proj.latitude_of_center


def _write_utm_params(crs_var, crs):
    #http://spatialreference.org/ref/epsg/32636/html/
    #http://cfconventions.org/Data/cf-conventions/cf-conventions-1.7/build/cf-conventions.html#appendix-grid-mappings at the transverse mercator section.
    crs_var.grid_mapping_name = 'transverse_mercator'
    crs_var.scale_factor_at_central_meridian = crs.proj.scale_factor
    crs_var.longitude_of_central_meridian = crs.proj.longitude_of_center
    crs_var.latitude_of_projection_origin = crs.proj.latitude_of_center

def _write_sinusoidal_params(crs_var, crs):
    crs_var.grid_mapping_name = 'sinusoidal'
    crs_var.longitude_of_central_meridian = crs.proj.central_meridian


CRS_PARAM_WRITERS = {
    'albers_conic_equal_area': _write_albers_params,
    'sinusoidal': _write_sinusoidal_params,
    'transverse_mercator': _write_utm_params
}


def _create_projected_grid_mapping_variable(nco, crs):
    grid_mapping_name = crs['PROJECTION'].lower()
    if grid_mapping_name not in CRS_PARAM_WRITERS:
        raise ValueError('{} CRS is not supported'.format(grid_mapping_name))

    crs_var = nco.createVariable('crs', 'i4')
    CRS_PARAM_WRITERS[grid_mapping_name](crs_var, crs)

    crs_var.false_easting = crs.proj.false_easting
    crs_var.false_northing = crs.proj.false_northing
    crs_var.long_name = crs['PROJCS']

    return crs_var


def _write_geographical_extents_attributes(nco, extent):
    geo_extents = extent.to_crs(CRS("EPSG:4326")).points
    geo_extents.append(geo_extents[0])
    nco.geospatial_bounds = "POLYGON((" + ", ".join("{0} {1}".format(*p) for p in geo_extents) + "))"
    nco.geospatial_bounds_crs = "EPSG:4326"

    nco.geospatial_lat_min = min(lat for lon, lat in geo_extents)
    nco.geospatial_lat_max = max(lat for lon, lat in geo_extents)
    nco.geospatial_lat_units = "degrees_north"
    nco.geospatial_lon_min = min(lon for lon, lat in geo_extents)
    nco.geospatial_lon_max = max(lon for lon, lat in geo_extents)
    nco.geospatial_lon_units = "degrees_east"

    # TODO: broken anyway...
    # nco.geospatial_lat_resolution = "{} degrees".format(abs(geobox.affine.e))
    # nco.geospatial_lon_resolution = "{} degrees".format(abs(geobox.affine.a))


def create_grid_mapping_variable(nco, crs):
    if crs.geographic:
        crs_var = _create_latlon_grid_mapping_variable(nco, crs)
    elif crs.projected:
        crs_var = _create_projected_grid_mapping_variable(nco, crs)
    else:
        raise ValueError('Unknown CRS')
    crs_var.semi_major_axis = crs.semi_major_axis
    crs_var.semi_minor_axis = crs.semi_minor_axis
    crs_var.inverse_flattening = crs.inverse_flattening
    crs_var.crs_wkt = crs.wkt

    crs_var.spatial_ref = crs.wkt

    dims = crs.dimensions
    xres, xoff = data_resolution_and_offset(nco[dims[1]])
    yres, yoff = data_resolution_and_offset(nco[dims[0]])
    crs_var.GeoTransform = [xoff, xres, 0.0, yoff, 0.0, yres]

    left, right = nco[dims[1]][0]-0.5*xres, nco[dims[1]][-1]+0.5*xres
    bottom, top = nco[dims[0]][0]-0.5*yres, nco[dims[0]][-1]+0.5*yres
    points = [[left, bottom], [left, top], [right, top], [right, bottom]]
    _write_geographical_extents_attributes(nco, GeoPolygon(points, crs))

    return crs_var


def write_flag_definition(variable, flags_definition):
    # write bitflag info
    # Functions for this are stored in Measurements
    variable.QA_index = describe_flags_def(flags_def=flags_definition)
    variable.flag_masks, variable.valid_range, variable.flag_meanings = flag_mask_meanings(flags_def=flags_definition)


def netcdfy_coord(data):
    if data.dtype.kind == 'M':
        return data.astype('<M8[s]').astype('double')
    return data


def netcdfy_data(data):
    if data.dtype.kind == 'S' and data.dtype.itemsize > 1:
        return data.view('S1').reshape(data.shape + (-1,))
    else:
        return data


def flag_mask_meanings(flags_def):
    # Filter out any multi-bit mask values since we can't handle them yet
    flags_def = {k: v for k, v in flags_def.items() if isinstance(v['bits'], numbers.Integral)}
    max_bit = max([bit_def['bits'] for bit_def in flags_def.values()])

    if max_bit >= 32:
        # GDAL upto and including 2.0 can't support int64 attributes...
        raise RuntimeError('Bit index too high: %s' % max_bit)

    valid_range = numpy.array([0, (2 ** max_bit - 1) + 2 ** max_bit], dtype='int32')

    masks = []
    meanings = []

    def by_bits(i):
        _, v = i
        return v['bits']

    for name, bitdef in sorted(flags_def.items(), key=by_bits):
        try:
            true_value = bitdef['values'][1]

            if true_value is True:
                meaning = name
            elif true_value is False:
                meaning = 'no_' + name
            else:
                meaning = true_value

            masks.append(2 ** bitdef['bits'])
            meanings.append(str(meaning))
        except KeyError:
            continue

    return numpy.array(masks, dtype='int32'), valid_range, ' '.join(meanings)
