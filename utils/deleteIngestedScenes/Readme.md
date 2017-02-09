# Delete ingested scenes

This is a sample script to delete ingested scenes from datacube. It requieres manual edition for each implementation and storage dataset type. 


## How to use this example?
- Both sh and sql files must be in the same folder. 
- The list of scenes must be at /tmp/a_eliminar.txt, in this file must be one scene "identifier" per line. In CDCol case, if tar.gz file name is LC80100582014079-SC20161026061538.tar.gz, scene identifier is LC80100582014079 (name part before '-').
- Bash script must be excecutable `chmod +x  deleteIngestedScenes.sh`
- Run the script:  `./deleteIngestedScenes.sh`
- Script may ask for sudo password.


This script will create a database backup named datacube.<date>.gz  (e.g. datacube.2017_02_03__15_16_30.gz)
Netcdf files are not deleted but moved to  /tmp/deleted_netcdf (In case of restore the backup)
