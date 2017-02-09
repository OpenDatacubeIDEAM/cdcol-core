-- @author: Christian Ariza-Porras - https://christian-ariza.netcdf
-- this script deletes, from datacube database, tiles generated from ingestion of scenes specified in /tmp/a_eliminar.txt file (one per line)
-- The script generate a list of netcdf files to be deleted. The list will be writed in /tmp/netcdf_para_borrar.tsv
BEGIN;
create temporary table t_malIngestados (image_id varchar primary key);
COPY t_malIngestados from  '/tmp/a_eliminar.txt';
create temporary table t_index as  select dataset_ref, regexp_replace(uri_body,'///source_storage/LS8_OLI_LEDAPS/tmp/(.*)/agdc-metadata.yaml',E'\\1')||'*.tar.gz' as f from agdc.dataset_location where regexp_replace(uri_body,'///source_storage/LS8_OLI_LEDAPS/tmp/(.*)/agdc-metadata.yaml',E'\\1') in (select image_id from t_malIngestados);

create temporary table t_ingested as select distinct dataset_ref from agdc.dataset_source where source_dataset_ref in (select dataset_ref from t_index );

--files that must be deleted (netcdf)
COPY(select uri_body from agdc.dataset_location where dataset_ref in (select  dataset_ref from t_ingested)) TO '/tmp/netcdf_para_borrar.tsv';
--delete from DATASET LOCATION

delete from agdc.dataset_location where dataset_ref in (select dataset_ref from t_ingested);
delete from agdc.dataset_location where dataset_ref in (select dataset_ref from t_index);
delete from agdc.dataset_source where dataset_ref in (select dataset_ref from t_ingested);
delete from agdc.dataset_source where dataset_ref in (select dataset_ref from t_index);
delete from agdc.dataset where id in (select dataset_ref from t_ingested union select dataset_ref from t_index);
COMMIT;