Data Access API
===============

For examples on how to use the API, see the Jupyter notebooks at:
http://nbviewer.jupyter.org/github/data-cube/agdc-v2/blob/develop/examples/notebooks/Datacube_Summary.ipynb


.. currentmodule:: datacube

.. _datacube-class:

Datacube Class
--------------

.. autosummary::
   :toctree: generate/

   Datacube


Higher Level User Functions
~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. autosummary::
   :toctree: generate/

   Datacube.list_products
   Datacube.list_measurements
   Datacube.load


Low-Level Internal Functions
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. autosummary::
   :toctree: generate/

   Datacube.product_observations
   Datacube.product_sources
   Datacube.product_data

   Datacube.measurement_data

.. _grid-workflow-class:

GridWorkflow Class
------------------

.. currentmodule:: datacube.api

.. autosummary::
   :toctree: generate/

   GridWorkflow


Higher Level User Functions
~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. autosummary::
   :toctree: generate/

   GridWorkflow.list_cells
   GridWorkflow.list_tiles
   GridWorkflow.load


Low-Level Internal Functions
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. autosummary::
   :toctree: generate/

   GridWorkflow.cell_observations
   GridWorkflow.cell_sources
   GridWorkflow.tile_sources



API for Analytics and Execution Engine
--------------------------------------

.. currentmodule:: datacube.api

.. autosummary::
   :toctree: generate/

    API.__init__
    API.list_products
    API.list_variables
    API.get_descriptor
    API.get_data



.. _query-class:

Query Class
-----------

.. currentmodule:: datacube.api.query

.. autosummary::
   :toctree: generate/

   Query


User Configuration
------------------
.. currentmodule:: datacube.config
.. autosummary::
  :toctree: generate/

  LocalConfig
  DEFAULT_CONF_PATHS
