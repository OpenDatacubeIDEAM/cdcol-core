#!/bin/bash
#@author: Christian Ariza-Porras - https://christian-ariza.netcdf
#Ensure that file '/tmp/a_eliminar.txt' exists and contains the id of the scenes that will be deleted from the datacube, one for line.
today=`date '+%Y_%m_%d__%H_%M_%S'`;
sudo su postgres -c "pg_dump -d datacube" |gzip > "datacube.$today.gz"
#Ensure unix EOL
sed -i 's/\r//g' '/tmp/a_eliminar.txt'

#ejecutar el script como el usuario postgres}
DIR="$( dirname '$0' )"
SCRIPT="$DIR/deleteIngestedScenes.sql"
echo $SCRIPT
sudo su postgres -c "psql -d datacube -f $SCRIPT"

#Delete netcdfs: 
echo "Removing files:"
mkdir -p /tmp/deleted_netcdf
while read line
do
mv $line /tmp/deleted_netcdf
echo "$line"
done <'/tmp/netcdf_para_borrar.tsv'

sudo mv '/tmp/netcdf_para_borrar.tsv' "/tmp/deleted_netcdf/borrados.$today.tsv"