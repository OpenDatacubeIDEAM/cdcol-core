.. _user_guide:

Recipes
=======

Plot RGB
--------

Uses
:class:`datacube.Datacube`
:class:`datacube.model.CRS`
:meth:`datacube.Datacube.load`
:meth:`xarray.Dataset.to_array`
:meth:`xarray.DataArray.transpose`
:meth:`xarray.DataArray.where`
:meth:`xarray.DataArray.all`
:func:`xarray.plot.imshow`


.. literalinclude:: recipes/plot_rgb.py
    :language: python

Multi-Product Time Series
-------------------------

Uses
:class:`datacube.Datacube`
:class:`datacube.model.DatasetType`
:meth:`datacube.index._datasets.DatasetTypeResource.get_by_name`
:meth:`datacube.Datacube.load`
:meth:`xarray.Dataset.isel`
:func:`xarray.concat`

.. literalinclude:: recipes/multi_prod_series.py
    :language: python

Line Transect
-------------

Uses
:class:`datacube.Datacube`
:class:`xarray.DataArray`
:class:`datacube.model.CRS`
:meth:`datacube.Datacube.load`
:meth:`xarray.Dataset.sel_points`

.. literalinclude:: recipes/line_transect.py
    :language: python
